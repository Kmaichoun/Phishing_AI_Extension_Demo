CREATE TABLE IF NOT EXISTS `ScanFeedback` (
    `FeedbackId` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `HistoryId` BIGINT UNSIGNED NOT NULL,
    `UserId` BIGINT UNSIGNED NOT NULL,
    `UserLabel` ENUM('dangerous','safe','unsure') NOT NULL,
    `ReviewStatus` ENUM('pending','confirmed','dismissed') NOT NULL DEFAULT 'pending',
    `ReviewNote` VARCHAR(1000) NOT NULL DEFAULT '',
    `ReviewedBy` BIGINT UNSIGNED NULL,
    `ReviewedAt` DATETIME(3) NULL,
    `CreatedAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    UNIQUE KEY `UX_Feedback_History_User` (`HistoryId`, `UserId`),
    INDEX `IX_Feedback_Review` (`ReviewStatus`, `CreatedAt`)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
