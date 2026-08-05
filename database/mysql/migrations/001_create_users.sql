/*
  Phish Radar AI - MySQL/MariaDB users
  PasswordHash stores an Argon2 hash. No plaintext password column is allowed.
*/

CREATE TABLE IF NOT EXISTS `Users`
(
    `UserId` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `Username` VARCHAR(50) NOT NULL,
    `NormalizedUsername` VARCHAR(50)
        GENERATED ALWAYS AS (LOWER(TRIM(`Username`))) STORED,
    `PasswordHash` VARCHAR(255) NOT NULL,
    `Email` VARCHAR(254) NOT NULL,
    `NormalizedEmail` VARCHAR(254)
        GENERATED ALWAYS AS (LOWER(TRIM(`Email`))) STORED,
    `Role` ENUM('user', 'admin') NOT NULL DEFAULT 'user',
    `IsActive` BOOLEAN NOT NULL DEFAULT TRUE,
    `EmailVerified` BOOLEAN NOT NULL DEFAULT FALSE,
    `CreatedAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `UpdatedAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    `LastLoginAt` DATETIME(3) NULL,

    CONSTRAINT `PK_Users` PRIMARY KEY (`UserId`),
    CONSTRAINT `UX_Users_NormalizedUsername` UNIQUE (`NormalizedUsername`),
    CONSTRAINT `UX_Users_NormalizedEmail` UNIQUE (`NormalizedEmail`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
