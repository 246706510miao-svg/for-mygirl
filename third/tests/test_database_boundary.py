from __future__ import annotations

import unittest

from third.agents.shared.config import validate_third_mysql_dsn


class ThirdDatabaseBoundaryTests(unittest.TestCase):
    def test_third_runtime_allows_private_workflow_database(self) -> None:
        dsn = "mysql+pymysql://third_user:third_password@127.0.0.1:3307/third_service"

        self.assertEqual(validate_third_mysql_dsn(dsn), dsn)

    def test_third_tests_allow_private_test_database(self) -> None:
        dsn = "mysql+pymysql://third_user:third_password@127.0.0.1:3307/third_test"

        self.assertEqual(validate_third_mysql_dsn(dsn), dsn)

    def test_third_rejects_business_database(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "for_mygirl_app"):
            validate_third_mysql_dsn("mysql+pymysql://third_user:third_password@127.0.0.1:3307/for_mygirl_app")

    def test_third_rejects_backend_database_account(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "backend_user"):
            validate_third_mysql_dsn("mysql+pymysql://backend_user:backend_password@127.0.0.1:3307/third_service")

    def test_third_rejects_unknown_mysql_database(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "third_service"):
            validate_third_mysql_dsn("mysql+pymysql://third_user:third_password@127.0.0.1:3307/random_db")


if __name__ == "__main__":
    unittest.main()
