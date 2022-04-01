try: 
    from kbr.dbase.postgres import *
except:
    raise ImportError("kbr.dbase.postgres is missing, to install please run: 'pip install git+https://github.com/brugger/kbr-tools-postgres.git'")

