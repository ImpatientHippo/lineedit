Default Usage:
===

import lineedit

```
editor = lineedit.Editor()
value = editor.edit( prefilled_text )
```

All "special" functions are defined as action functions inside editor.
You can inhert from Editor in order to overload those.


Bugs
===

Does not handle line breaks and wrapping well. You can limit the size
of the input field lineedit.Editor(max=20) in order to mitigate.
