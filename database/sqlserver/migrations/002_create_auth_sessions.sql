/*
  Phish Radar AI - server-side authentication sessions
  Migration: 002

  Run this after 001_create_auth_schema.sql.
  Only SHA-256 hashes of random session tokens are stored in SQL Server.
*/

USE [PhishRadarDB];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'[auth].[Sessions]', N'U') IS NULL
    BEGIN
        CREATE TABLE [auth].[Sessions]
        (
            [SessionId] UNIQUEIDENTIFIER NOT NULL
                CONSTRAINT [DF_Sessions_SessionId] DEFAULT (NEWSEQUENTIALID()),
            [UserId] BIGINT NOT NULL,
            [UserDeviceId] BIGINT NOT NULL,
            [TokenHash] BINARY(32) NOT NULL,
            [CreatedAt] DATETIME2(3) NOT NULL
                CONSTRAINT [DF_Sessions_CreatedAt] DEFAULT (SYSUTCDATETIME()),
            [LastSeenAt] DATETIME2(3) NOT NULL
                CONSTRAINT [DF_Sessions_LastSeenAt] DEFAULT (SYSUTCDATETIME()),
            [ExpiresAt] DATETIME2(3) NOT NULL,
            [RevokedAt] DATETIME2(3) NULL,

            CONSTRAINT [PK_Sessions]
                PRIMARY KEY CLUSTERED ([SessionId]),
            CONSTRAINT [FK_Sessions_Users]
                FOREIGN KEY ([UserId])
                REFERENCES [auth].[Users] ([UserId]),
            CONSTRAINT [FK_Sessions_UserDevices]
                FOREIGN KEY ([UserDeviceId])
                REFERENCES [auth].[UserDevices] ([UserDeviceId])
                ON DELETE CASCADE,
            CONSTRAINT [CK_Sessions_Expiry]
                CHECK ([ExpiresAt] > [CreatedAt]),
            CONSTRAINT [CK_Sessions_RevokedAt]
                CHECK ([RevokedAt] IS NULL OR [RevokedAt] >= [CreatedAt])
        );
    END;

    IF NOT EXISTS
    (
        SELECT 1 FROM sys.indexes
        WHERE [object_id] = OBJECT_ID(N'[auth].[Sessions]')
          AND [name] = N'UX_Sessions_TokenHash'
    )
    BEGIN
        CREATE UNIQUE INDEX [UX_Sessions_TokenHash]
            ON [auth].[Sessions] ([TokenHash]);
    END;

    IF NOT EXISTS
    (
        SELECT 1 FROM sys.indexes
        WHERE [object_id] = OBJECT_ID(N'[auth].[Sessions]')
          AND [name] = N'IX_Sessions_User_ExpiresAt'
    )
    BEGIN
        CREATE INDEX [IX_Sessions_User_ExpiresAt]
            ON [auth].[Sessions] ([UserId], [ExpiresAt] DESC)
            INCLUDE ([UserDeviceId], [LastSeenAt], [RevokedAt]);
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
