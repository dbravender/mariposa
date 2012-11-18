# from http://code.google.com/p/sv-subversion/
# (c) 2007 Dan Bravender, Kumar McMillan and Luke Opperman
# licensed under the GNU GPL 2.0


class Commands(object):
    ''' a container and decorator for commands '''
    def __init__(self):
        self.commands = {}
        self.help = {}

    def __call__(self, func=None, aliases=None):
        ''' can be called as @command or @command(aliases=['x', 'y'])'''
        def _command(func):
            fname = func.__name__
            self.commands[fname] = func
            self.help[fname] = func.__doc__
            for alias in aliases and aliases or []:
                self.commands[alias] = func
                self.help[alias] = "(alias for %s)" % fname
            return func
        if func:
            return _command(func)
        return _command

command = Commands()
