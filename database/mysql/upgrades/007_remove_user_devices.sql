-- Phish Radar AI: remove legacy device storage from the selected database.
-- Stop the old backend before importing, then deploy the updated backend.
-- Users, sessions and scan history are retained. Device records are removed.
-- Intended for the project's shared-hosting schema without foreign keys.

SET @phish_radar_ddl = IF(
    EXISTS(SELECT 1 FROM information_schema.columns
           WHERE table_schema = DATABASE() AND table_name = 'Sessions'
             AND column_name = 'UserDeviceId'),
    'ALTER TABLE `Sessions` DROP COLUMN `UserDeviceId`',
    'SELECT 1'
);
PREPARE phish_radar_stmt FROM @phish_radar_ddl;
EXECUTE phish_radar_stmt;
DEALLOCATE PREPARE phish_radar_stmt;

SET @phish_radar_ddl = IF(
    EXISTS(SELECT 1 FROM information_schema.columns
           WHERE table_schema = DATABASE() AND table_name = 'SearchHistory'
             AND column_name = 'UserDeviceId'),
    'ALTER TABLE `SearchHistory` DROP COLUMN `UserDeviceId`',
    'SELECT 1'
);
PREPARE phish_radar_stmt FROM @phish_radar_ddl;
EXECUTE phish_radar_stmt;
DEALLOCATE PREPARE phish_radar_stmt;

DROP TABLE IF EXISTS `UserDevices`;

SET @phish_radar_ddl = IF(
    EXISTS(SELECT 1 FROM information_schema.tables
           WHERE table_schema = DATABASE() AND table_name = 'AuditEvents'),
    'DELETE FROM `AuditEvents` WHERE `TargetType` = ''device'' OR `Action` = ''device.revoke''',
    'SELECT 1'
);
PREPARE phish_radar_stmt FROM @phish_radar_ddl;
EXECUTE phish_radar_stmt;
DEALLOCATE PREPARE phish_radar_stmt;
