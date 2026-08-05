/*
  Optional: create the MySQL/MariaDB database when the account has permission.

  Shared hosting normally creates the database in its control panel first.
  In that case, do not run this file; select ip_std6730202581 in phpMyAdmin
  and run the files in migrations/ instead.
*/

CREATE DATABASE IF NOT EXISTS `ip_std6730202581`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

