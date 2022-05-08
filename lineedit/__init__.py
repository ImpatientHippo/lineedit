import termios   # does the terminal magic
import atexit    # cleanup
import sys       # access to stdin
import re        # word wide movements
import shutil    # obtein terminal size

# Key escape sequences which are (possible) edit comands

UNKNOWN = None
UP = 1
DOWN = 2
RIGHT = 3
LEFT = 4
HOME = 5
END = 6
INSERT = 7
DELETE = 8
PAGE_UP = 9
PAGE_DOWN = 10
CTRL_LEFT = 11
CTRL_RIGHT = 12

def raw_mode( raw, fd = sys.stdin ):
  (iflag, oflag, cflag, lflag, ispeed, ospeed, cc) = termios.tcgetattr( fd )
  if raw:
    lflag &= ~termios.ECHO
    lflag &= ~termios.ICANON
  else:
    lflag |= termios.ECHO
    lflag |= termios.ICANON

  termios.tcsetattr( fd, termios.TCSANOW, [
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc
  ])

def setup_raw( fd = sys.stdin ):
  atexit.register( lambda : raw_mode(False,fd) )
  raw_mode(True,fd)

SEQ = {
  "A" : UP,
  "B" : DOWN,
  "C" : RIGHT,
  "D" : LEFT,
  "H" : HOME,
  "F" : END,
  "2~": INSERT,
  "3~": DELETE,
  "5~": PAGE_UP,
  "6~": PAGE_DOWN,
  "1;5C": CTRL_RIGHT,
  "1;5D": CTRL_LEFT
}

ESC = "\x1b"
ESC_SAVE_CURSOR = "\x1b[s"
ESC_RESTORE_CURSOR = "\x1b[u"

CS_PARAMETER = "0123456789:;<=>?"
CS_INTERMEDIATE = "\"#$%&'()*+,-./"
CS_FINAL = "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~"

def esc2str( fd = sys.stdin ):
  """
    Parse the rest of the ESC sequence (after having read the ESC)
    Returns the full escape sequence back (without the CSI = "ESC [")
  """
  next = fd.read(1)
  if next!='[': return None
  buf = ""
  next = fd.read(1)
  while CS_PARAMETER.find(next)>=0:
    buf += next
    next = fd.read(1)
  while CS_INTERMEDIATE.find(next)>=0:
    buf += next
    next = fd.read(1)
  if CS_FINAL.find(next)>=0:
    buf += next
    return buf
  raise f"Malformed ESC Sequence '{buf}'"

def parse_esc( fd = sys.stdin ):
  seq = esc2str( fd )
  return SEQ.get(seq) or UNKNOWN

class Key:
  """
    Represents a single keystoke from fd.
    Analyses ESC sequences (partial support for most common strokes)
  """
  def __init__(self,fd=sys.stdin):
    key = fd.read(1)
    if key != ESC:
      self.char = key
      self.cmd = None
    else:
      self.char = None
      self.cmd = parse_esc(fd)

def read( fd=sys.stdin ):
  return Key(fd)

def emit( text ):
  """ Variant of print suitable for raw output """
  print( text, end="", flush=True )

class Editor:

  def __init__(self,fd=sys.stdin,max=None):
    """
      Editor reading keyboard input from fd
      max is the maximun text length, should net be larger
      than the terminal. Editor tries to determine max length
      but this is not fool proof by far.
    """
    self.fd = fd
    self.maxlen = max or shutil.get_terminal_size().columns-1
    self.key_cmds = {
      '\n': self.enter,
      '\t': self.tab,
      '\x7f': self.backspace,
      '\x08': self.backspace, # ctrl H
      '\x0b': self.kill_post, # ctrl K
      '\x17': self.delete_word, # ctrl W
    }
    self.esc_cmds = {
      LEFT: self.left,
      RIGHT: self.right,
      HOME: self.home,
      END: self.end,
      DELETE: self.delete,
      CTRL_LEFT: self.word_left,
      CTRL_RIGHT: self.word_right,
    }

  def show( self, erase=0 ):
    """
      Show the current edit line buffer.
      Add "erase" spaces (in order to update after deletion)
    """
    emit( ESC_RESTORE_CURSOR )
    emit( self.pre )
    emit( self.post )
    emit( ' '*erase )
    back = len(self.post) + erase
    if back>0: emit( f"{ESC}[{back}D" )

  def handle_char( self, char ):
    """
      Adds a charcater to the buffer and redisplays.
    """
    if self.maxlen<0 or len(self.pre+self.post)<self.maxlen:
      self.pre = self.pre + char
      self.show()

  def edit( self, text="", post="" ):
    """
      ** Main Function for Editor **
      Edit text+post, with the cursort starting after text
      Returns the edited text.
      May throw keyboard Error after ctrl c
    """
    self.pre = text
    self.post = post
    emit( ESC_SAVE_CURSOR )
    self.show()
    self.running = True
    while self.running:
      key = read(self.fd)

      if key.char is not None:
        cmdfunc = self.key_cmds.get(key.char)
        if( cmdfunc ):
          cmdfunc()
        elif ord(key.char)>=32:
          self.handle_char( key.char )

      elif key.cmd is not None:
        cmdfunc = self.esc_cmds.get(key.cmd)
        if cmdfunc:
          cmdfunc()
          self.show()
    return self.pre + self.post

  """ Handlers for specific actions """

  def left( self ):
    """ Cursor moves one char to the left """
    if self.pre=="": return
    self.post = self.pre[-1]+self.post
    self.pre = self.pre[0:-1]

  def right( self ):
    """ Cursor moves one char to the right """
    if self.post=="": return
    self.pre = self.pre + self.post[0]
    self.post = self.post[1:]

  def home( self ):
    """ Cursor moves to the beginning of the line """
    self.post = self.pre + self.post
    self.pre = ""

  def end( self ):
    """ Cursor moves to the end of the line """
    self.pre = self.pre + self.post
    self.post = ""

  def delete( self ):
    """ Delete char under/behind cursor """
    if len(self.post)>0: self.post = self.post[1:]
    self.show(1)

  def delete_word( self ):
    """ Delete word before cursor """
    boundaries = list(re.finditer(r"\b",self.pre))
    if len(boundaries)>1:
      kill = len(self.pre) - boundaries[-2].start()
      self.pre = self.pre[ 0 : boundaries[-2].start() ]
      self.show(kill)

  def word_left( self ):
    """ Cursor moves one word to the left """
    boundaries = list(re.finditer(r"\b",self.pre))
    if len(boundaries)>1:
      self.post = self.pre[ boundaries[-2].start() : ] + self.post
      self.pre = self.pre[ 0 : boundaries[-2].start() ]
      self.show()

  def word_right( self ):
    """ Cursor moves one word to the right """
    boundaries = list(re.finditer(r"\b",self.post))
    if len(boundaries)>1:
      self.pre = self.pre + self.post[ 0 : boundaries[1].start()]
      self.post = self.post[ boundaries[1].start() : ]
      self.show()

  def up( self ):
    """ TODO: previous in history """
    pass

  def down( self ):
    """ TODO: next in history """
    pass

  def tab( self ):
    """ TODO: trigger some kind of completion """
    pass

  def enter( self ):
    """ Finish editing """
    self.running = False

  def backspace( self ):
    """ Delete char before cursor """
    if len(self.pre)>0: self.pre = self.pre[0:-1]
    self.show(1)

  def kill_post( self ):
    """ Delete everything behind cursor """
    l = len(self.post)
    self.post = ""
    self.show(l)
