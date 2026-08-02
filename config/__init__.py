try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:
    # PyMySQL is a prod-only dependency (requirements/prod.txt) -- local dev
    # runs on SQLite and never imports it.
    pass
