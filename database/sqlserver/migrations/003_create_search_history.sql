/*
  Phish Radar AI - per-user URL search history
  Migration: 003

  The stored URL removes credentials, query strings and fragments. A SHA-256
  hash of that sanitized URL is retained for correlation; no hash of the
  sensitive raw query string is stored.
*/

USE [PhishRadarDB];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'[auth].[SearchHistory]', N'U') IS NULL
    BEGIN
        CREATE TABLE [auth].[SearchHistory]
        (
            [HistoryId] BIGINT IDENTITY(1, 1) NOT NULL,
            [UserId] BIGINT NOT NULL,
            [UserDeviceId] BIGINT NOT NULL,
            [Url] NVARCHAR(2048) NOT NULL,
            [UrlHash] BINARY(32) NOT NULL,
            [Hostname] NVARCHAR(253) NOT NULL,
            [RuleScore] TINYINT NOT NULL,
            [MlScore] TINYINT NULL,
            [FinalScore] TINYINT NOT NULL,
            [Alpha] DECIMAL(5, 4) NULL,
            [DecisionThreshold] DECIMAL(6, 2) NULL,
            [DetectionLabel] NVARCHAR(20) NULL,
            [ModelStatus] NVARCHAR(50) NULL,
            [Source] NVARCHAR(30) NOT NULL
                CONSTRAINT [DF_SearchHistory_Source] DEFAULT (N'web-app'),
            [CreatedAt] DATETIME2(3) NOT NULL
                CONSTRAINT [DF_SearchHistory_CreatedAt] DEFAULT (SYSUTCDATETIME()),

            CONSTRAINT [PK_SearchHistory]
                PRIMARY KEY CLUSTERED ([HistoryId]),
            CONSTRAINT [FK_SearchHistory_Users]
                FOREIGN KEY ([UserId]) REFERENCES [auth].[Users] ([UserId]) ON DELETE CASCADE,
            CONSTRAINT [FK_SearchHistory_UserDevices]
                FOREIGN KEY ([UserDeviceId]) REFERENCES [auth].[UserDevices] ([UserDeviceId]),
            CONSTRAINT [CK_SearchHistory_Url_Length]
                CHECK (LEN(LTRIM(RTRIM([Url]))) BETWEEN 1 AND 2048),
            CONSTRAINT [CK_SearchHistory_Hostname_Length]
                CHECK (LEN(LTRIM(RTRIM([Hostname]))) BETWEEN 1 AND 253),
            CONSTRAINT [CK_SearchHistory_RuleScore]
                CHECK ([RuleScore] BETWEEN 0 AND 100),
            CONSTRAINT [CK_SearchHistory_MlScore]
                CHECK ([MlScore] IS NULL OR [MlScore] BETWEEN 0 AND 100),
            CONSTRAINT [CK_SearchHistory_FinalScore]
                CHECK ([FinalScore] BETWEEN 0 AND 100),
            CONSTRAINT [CK_SearchHistory_Alpha]
                CHECK ([Alpha] IS NULL OR [Alpha] BETWEEN 0 AND 1),
            CONSTRAINT [CK_SearchHistory_Threshold]
                CHECK ([DecisionThreshold] IS NULL OR [DecisionThreshold] BETWEEN 0 AND 100),
            CONSTRAINT [CK_SearchHistory_DetectionLabel]
                CHECK ([DetectionLabel] IS NULL OR [DetectionLabel] IN (N'safe', N'phishing')),
            CONSTRAINT [CK_SearchHistory_Source]
                CHECK ([Source] IN (N'web-app', N'qr-scanner'))
        );
    END;

    IF NOT EXISTS
    (
        SELECT 1 FROM sys.indexes
        WHERE [object_id] = OBJECT_ID(N'[auth].[SearchHistory]')
          AND [name] = N'IX_SearchHistory_User_CreatedAt'
    )
    BEGIN
        CREATE INDEX [IX_SearchHistory_User_CreatedAt]
            ON [auth].[SearchHistory] ([UserId], [CreatedAt] DESC)
            INCLUDE ([Hostname], [RuleScore], [MlScore], [FinalScore], [DetectionLabel], [Source]);
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT [SchemaName] = SCHEMA_NAME([schema_id]), [TableName] = [name]
FROM sys.tables
WHERE [schema_id] = SCHEMA_ID(N'auth')
ORDER BY [name];
GO
