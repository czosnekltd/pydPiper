# lcd_display_driver - base class for lcd or oled 16x2 or 20x4 displays

import abc, fonts, time
import math
from PIL import Image

try:
	import RPi.GPIO as GPIO
	GPIO_INSTALLED=True
except:
	print "GPIO not installed"
	GPIO_INSTALLED=False

class lcd_display_driver:
	__metaclass__ = abc.ABCMeta

	# Need to decide whether custom fonts live in the driver or the display.
	# THinking right now, they should live in the base driver class.

	FONTS_SUPPORTED = True

	def __init__(self, rows, columns, enable_duration):
		self.rows = rows
		self.columns = columns
		self.enable_duration = enable_duration
        self._exec_time = 1e-6 * 50
        self._pulse_time = 1e-6 * 50
		# Write custom fonts if the display supports them
		# Fonts are currenty 5x8
#		try:
#			self.loadcustomchars(0, fonts.size5x8.player.fontpkg)
#		except RuntimeError:
#			# Custom fonts not supported
#			self.FONTS_SUPPORTED = False
#			pass

    def command(self, *cmd, exec_time=None, only_low_bits=False):
        """
        Sends a command or sequence of commands through to the serial interface.
        If operating in four bit mode, expands each command from one byte
        values (8 bits) to two nibble values (4 bits each)

        :param cmd: A spread of commands.
        :type cmd: int
        :param exec_time: Amount of time to wait for the command to finish
            execution.  If not provided, the device default will be used instead
        :type exec_time: float
        :param only_low_bits: If ``True``, only the lowest four bits of the command
            will be sent.  This is necessary on some devices during initialization
        :type only_low_bits: bool
        """
        cmd = cmd if only_low_bits else \
            self.bytes_to_nibbles(cmd)
        self._write(cmd, GPIO.LOW)
        sleep(exec_time or self._exec_time)

    def data(self, data):
        """
        Sends a data byte or sequence of data bytes through to the bus.
        If the bus is in four bit mode, only the lowest 4 bits of the data
        value will be sent.

        This means that the device needs to send high and low bits separately
        if the device is operating using a 4 bit bus (e.g. to send a 0x32 in
        4 bit mode the device would use ``data([0x03, 0x02])``).

        :param data: A data sequence.
        :type data: list, bytearray
        """
        self._write(data, GPIO.HIGH)

    def bytes_to_nibbles(data):
        """
        Utility function to take a list of bytes (8 bit values) and turn it into
        a list of nibbles (4 bit values)

        :param data: a list of 8 bit values that will be converted
        :type data: list
        :return: a list of 4 bit values
        :rtype: list
        """
        return [f(x) for x in data for f in (lambda x: x >> 4, lambda x: 0x0F & x)]

    def _write(self, data, mode):
        GPIO.output(self._RS, mode)
        GPIO.output(self._E, GPIO.LOW)
        for value in data:
            for i in range(4):
                GPIO.output(self.pins_db[i], (value >> i) & 0x01)
            GPIO.output(self._E, GPIO.HIGH)
            sleep(self._pulse_time)
            GPIO.output(self._E, GPIO.LOW)

	def write4bits(self, bits, char_mode=False):

		if GPIO_INSTALLED:
#			self.delayMicroseconds(1000)
			GPIO.output(self.pin_rs, char_mode)
			GPIO.output(self.pins_db[::-1][0], bits & 0x80)
			GPIO.output(self.pins_db[::-1][1], bits & 0x40)
			GPIO.output(self.pins_db[::-1][2], bits & 0x20)
			GPIO.output(self.pins_db[::-1][3], bits & 0x10)
			self.pulseEnable()

			GPIO.output(self.pins_db[::-1][0], bits & 0x08)
			GPIO.output(self.pins_db[::-1][1], bits & 0x04)
			GPIO.output(self.pins_db[::-1][2], bits & 0x02)
			GPIO.output(self.pins_db[::-1][3], bits & 0x01)
			self.pulseEnable()


	def writeonly4bits(self, bits, char_mode=False):

		# Version of write that only sends a 4 bit value
		if bits > 15: return

		if GPIO_INSTALLED:
			GPIO.output(self.pin_rs, char_mode)
			GPIO.output(self.pins_db[::-1][0], bits & 0x08)
			GPIO.output(self.pins_db[::-1][1], bits & 0x04)
			GPIO.output(self.pins_db[::-1][2], bits & 0x02)
			GPIO.output(self.pins_db[::-1][3], bits & 0x01)
			self.pulseEnable()


	def delayMicroseconds(self, microseconds):
		seconds = microseconds / 1000000.0 # divide microseconds by 1 million for seconds
		time.sleep(seconds)


	def pulseEnable(self):
		# the pulse timing in the 16x2_oled_volumio 2.py file is 1000/500
		# the pulse timing in the original version of this file is 10/10
		# with a 100 post time for setting

#		GPIO.output(self.pin_e, False)
#		self.delayMicroseconds(.1) # 1 microsecond pause - enable pulse must be > 450ns
		GPIO.output(self.pin_e, True)
		self.delayMicroseconds(self.enable_duration) # 1 microsecond pause - enable pulse must be > 450ns
		GPIO.output(self.pin_e, False)


	def getframe(self,image,x,y,width,height):
		# Returns an array of arrays
		# [
		#   [ ], # Array of bytes for line 0
		#   [ ]  # Array of bytes for line 1
		#				 ...
		#   [ ]  # Array of bytes for line n
		# ]

		# Select portion of image to work with
		img = image.convert("1")

		width, height = img.size
		bheight = int(math.ceil(height / 8.0))
		imgdata = list(img.getdata())


		retval = []	# The variable to hold the return value (an array of byte arrays)
		retline = [0]*width # Line to hold the first byte of image data
		bh = 0 # Used to determine when we've consumed a byte worth of the line

		# Perform a horizontal iteration of the image data
		for i in range(0,height):
			for j in range(0,width):
				# if the value is true then mask a bit into the byte within retline
				if imgdata[(i*width)+j]:
					try:
						retline[j] |= 1<<bh
					except IndexError as e:
						# WTF
						print "width = {0}".format(width)
						raise e
			# If we've written a full byte, start a new retline
			bh += 1
			if bh == 8: # We reached a byte boundary
				bh = 0
				retval.append(retline)
				retline = [0]*width
		if bh > 0:
			retval.append(retline)

		return retval

	def switchcustomchars(self, fontpkg):
		if self.FONTS_SUPPORTED:
			try:
				self.loadcustomchars(0, fontpkg)
			except RuntimeError:
				self.FONTS_SUPPORTED = False
				pass

	@abc.abstractmethod
	def message(self, message, row, col):
		# Sends a message for the dispay to show on row at col
		# Messages must be UTF-8 encoded
		# Must throw IndexError if row or col is out of range for the display
		return

	@abc.abstractmethod
	def clear(self):
		# clears the display
		return


	def command(self, cmd):
		# Sends a command to the display
		# Must support the following commands...
			# CLEAR - Clears the display
			# DISPLAYON - Turns display on
			# DISPLAYOFF - Turns display off
			# CURSORON - Turns the underine cursor on
			# CURSOROFF - Turns the underline cursor off
			# BLINKON - Turns blinking on
			# BLINKOFF - Turns blinking off

		if cmd == u"CLEAR":
			self.clear()
		elif cmd == u"DISPLAYON":
			self.displayon()
		elif cmd == u"DISPLAYOFF":
			self.displayoff()
		elif cmd == u"CURSORON":
			self.cursoron()
		elif cmd == u"CURSOROFF":
			self.cursoroff()
		elif cmd == u"BLINKON":
			self.blinkon()
		elif cmd == u"BLINKOFF":
			self.blinkoff()
		else:
			raise RuntimeError(u'Command {0} not supported'.format(cmd))

	@abc.abstractmethod
	def cleanup(self):
		# If there are any steps needed to restore system state on exit, this is the place to do it.
		return

	@abc.abstractmethod
	def loadcustomchars(self, char, fontdata):
		# Write an array of custom characters starting at position char within
		# the CGRAM region.
		# Char should be an integer between 0 and 255
		# fontdata should be an array of fonts which is are arrays of font data
		# Must throw RuntimeError('Command loadcustomchars not supported')
		# if display doesn't allow custom characters
		return
