/*
  Phish Radar AI - sanitized URL history and Risk Model audit data

  Url never stores credentials, query strings or fragments. LayerResults is
  serialized JSON from the Backend and is stored as LONGTEXT for broad
  MySQL/MariaDB hosting compatibility.

  Shared-hosting compatible: UserId remains an indexed logical relationship,
  without FOREIGN KEY or CHECK clauses that require privileges
  or parser support not provided by some hosting plans.
*/

CREATE TABLE IF NOT EXISTS `SearchHistory`
(
    `HistoryId` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `UserId` BIGINT UNSIGNED NOT NULL,
    `Url` VARCHAR(2048) NOT NULL,
    `UrlHash` BINARY(32) NOT NULL,
    `Hostname` VARCHAR(253) NOT NULL,
    `RuleScore` TINYINT UNSIGNED NOT NULL,
    `MlScore` TINYINT UNSIGNED NULL,
    `FinalScore` TINYINT UNSIGNED NOT NULL,
    `Alpha` DECIMAL(5, 4) NULL,
    `DecisionThreshold` DECIMAL(6, 2) NULL,
    `DetectionLabel` ENUM('safe', 'phishing') NULL,
    `ModelStatus` VARCHAR(50) NULL,
    `Source` ENUM('web-app', 'qr-scanner') NOT NULL DEFAULT 'web-app',
    `RiskProbability` DECIMAL(9, 8) NULL,
    `RiskScore` TINYINT UNSIGNED NULL,
    `Decision` ENUM('allow', 'warn', 'block') NULL,
    `WarningThreshold` DECIMAL(6, 2) NULL,
    `BlockingThreshold` DECIMAL(6, 2) NULL,
    `ModelVersion` VARCHAR(100) NULL,
    `PolicyVersion` VARCHAR(100) NULL,
    `FeatureSchemaVersion` VARCHAR(100) NULL,
    `LayerResults` LONGTEXT NULL,
    `CreatedAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    CONSTRAINT `PK_SearchHistory` PRIMARY KEY (`HistoryId`),
    INDEX `IX_SearchHistory_User_CreatedAt` (`UserId`, `CreatedAt`, `HistoryId`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
