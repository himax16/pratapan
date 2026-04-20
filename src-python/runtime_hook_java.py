import os
import sys

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _jre = os.path.join(sys._MEIPASS, 'jre')
    if os.path.isdir(_jre):
        os.environ['JAVA_HOME'] = _jre
        _bin = os.path.join(_jre, 'bin')
        if _bin not in os.environ.get('PATH', ''):
            os.environ['PATH'] = _bin + os.pathsep + os.environ.get('PATH', '')
