from navconfig import config


def test_set():
    mysql_driver = config.get('MYSQL_DRIVER')
    print('Driver:', mysql_driver)
    config.set('MYSQL_DRIVER', 'mysqlclient')
    mysql_driver = config.get('MYSQL_DRIVER')
    print('Driver:', mysql_driver)
    # set a new complex variable:
    a = {"user": 1, "username": "test"}
    config.set('TEST', a)
    print(config.get('TEST'))


if __name__ == '__main__':
    test_set()
