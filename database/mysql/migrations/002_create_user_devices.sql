/*
  Phish Radar AI - devices associated with user accounts
  DeviceKeyHash stores SHA-256 output, never the device token itself.

  Shared-hosting compatible: no FOREIGN KEY or CHECK clauses are used because
  restricted database accounts may not have the REFERENCES privilege.
*/

CREATE TABLE IF NOT EXISTS `UserDevices`
(
    `UserDeviceId` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `UserId` BIGINT UNSIGNED NOT NULL,
    `DeviceName` VARCHAR(200) NOT NULL,
    `DeviceKeyHash` BINARY(32) NULL,
    `IsTrusted` BOOLEAN NOT NULL DEFAULT FALSE,
    `IsRevoked` BOOLEAN NOT NULL DEFAULT FALSE,
    `FirstSeenAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `LastSeenAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `RevokedAt` DATETIME(3) NULL,

    CONSTRAINT `PK_UserDevices` PRIMARY KEY (`UserDeviceId`),
    CONSTRAINT `UX_UserDevices_User_DeviceKeyHash`
        UNIQUE (`UserId`, `DeviceKeyHash`),
    INDEX `IX_UserDevices_UserId` (`UserId`),
    INDEX `IX_UserDevices_User_LastSeenAt` (`UserId`, `LastSeenAt`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
