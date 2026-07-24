/*
  Phish Radar AI - SQL Server authentication schema
  Migration: 001

  This script creates the database and authentication tables only.
  It does not create a SQL Server login and does not insert an admin account.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_ID(N'PhishRadarDB') IS NULL
BEGIN
    EXEC(N'CREATE DATABASE [PhishRadarDB];');
END;
GO

USE [PhishRadarDB];
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET ARITHABORT ON;
SET NUMERIC_ROUNDABORT OFF;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF SCHEMA_ID(N'auth') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA [auth] AUTHORIZATION [dbo];');
END;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'[auth].[Users]', N'U') IS NULL
    BEGIN
        CREATE TABLE [auth].[Users]
        (
            [UserId] BIGINT IDENTITY(1, 1) NOT NULL,
            [Username] NVARCHAR(50) NOT NULL,
            [NormalizedUsername] AS LOWER(LTRIM(RTRIM([Username]))) PERSISTED,
            [PasswordHash] NVARCHAR(255) NOT NULL,
            [Email] NVARCHAR(254) NOT NULL,
            [NormalizedEmail] AS LOWER(LTRIM(RTRIM([Email]))) PERSISTED,
            [Role] NVARCHAR(20) NOT NULL
                CONSTRAINT [DF_Users_Role] DEFAULT (N'user'),
            [IsActive] BIT NOT NULL
                CONSTRAINT [DF_Users_IsActive] DEFAULT ((1)),
            [EmailVerified] BIT NOT NULL
                CONSTRAINT [DF_Users_EmailVerified] DEFAULT ((0)),
            [CreatedAt] DATETIME2(3) NOT NULL
                CONSTRAINT [DF_Users_CreatedAt] DEFAULT (SYSUTCDATETIME()),
            [UpdatedAt] DATETIME2(3) NOT NULL
                CONSTRAINT [DF_Users_UpdatedAt] DEFAULT (SYSUTCDATETIME()),
            [LastLoginAt] DATETIME2(3) NULL,
            [RowVersion] ROWVERSION NOT NULL,

            CONSTRAINT [PK_Users]
                PRIMARY KEY CLUSTERED ([UserId]),
            CONSTRAINT [CK_Users_Username_Length]
                CHECK (LEN(LTRIM(RTRIM([Username]))) BETWEEN 3 AND 50),
            CONSTRAINT [CK_Users_Email_Length]
                CHECK (LEN(LTRIM(RTRIM([Email]))) BETWEEN 3 AND 254),
            CONSTRAINT [CK_Users_PasswordHash_NotEmpty]
                CHECK (LEN(LTRIM(RTRIM([PasswordHash]))) > 0),
            CONSTRAINT [CK_Users_Role]
                CHECK ([Role] IN (N'user', N'admin'))
        );
    END;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.indexes
        WHERE [object_id] = OBJECT_ID(N'[auth].[Users]')
          AND [name] = N'UX_Users_NormalizedUsername'
    )
    BEGIN
        CREATE UNIQUE INDEX [UX_Users_NormalizedUsername]
            ON [auth].[Users] ([NormalizedUsername]);
    END;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.indexes
        WHERE [object_id] = OBJECT_ID(N'[auth].[Users]')
          AND [name] = N'UX_Users_NormalizedEmail'
    )
    BEGIN
        CREATE UNIQUE INDEX [UX_Users_NormalizedEmail]
            ON [auth].[Users] ([NormalizedEmail]);
    END;

    IF OBJECT_ID(N'[auth].[UserDevices]', N'U') IS NULL
    BEGIN
        CREATE TABLE [auth].[UserDevices]
        (
            [UserDeviceId] BIGINT IDENTITY(1, 1) NOT NULL,
            [UserId] BIGINT NOT NULL,
            [DeviceName] NVARCHAR(200) NOT NULL,
            [DeviceKeyHash] BINARY(32) NULL,
            [IsTrusted] BIT NOT NULL
                CONSTRAINT [DF_UserDevices_IsTrusted] DEFAULT ((0)),
            [IsRevoked] BIT NOT NULL
                CONSTRAINT [DF_UserDevices_IsRevoked] DEFAULT ((0)),
            [FirstSeenAt] DATETIME2(3) NOT NULL
                CONSTRAINT [DF_UserDevices_FirstSeenAt] DEFAULT (SYSUTCDATETIME()),
            [LastSeenAt] DATETIME2(3) NOT NULL
                CONSTRAINT [DF_UserDevices_LastSeenAt] DEFAULT (SYSUTCDATETIME()),
            [RevokedAt] DATETIME2(3) NULL,
            [RowVersion] ROWVERSION NOT NULL,

            CONSTRAINT [PK_UserDevices]
                PRIMARY KEY CLUSTERED ([UserDeviceId]),
            CONSTRAINT [FK_UserDevices_Users]
                FOREIGN KEY ([UserId])
                REFERENCES [auth].[Users] ([UserId])
                ON DELETE CASCADE,
            CONSTRAINT [CK_UserDevices_DeviceName_Length]
                CHECK (LEN(LTRIM(RTRIM([DeviceName]))) BETWEEN 1 AND 200),
            CONSTRAINT [CK_UserDevices_RevokedAt]
                CHECK (
                    ([IsRevoked] = 0 AND [RevokedAt] IS NULL)
                    OR ([IsRevoked] = 1 AND [RevokedAt] IS NOT NULL)
                )
        );
    END;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.indexes
        WHERE [object_id] = OBJECT_ID(N'[auth].[UserDevices]')
          AND [name] = N'UX_UserDevices_User_DeviceKeyHash'
    )
    BEGIN
        CREATE UNIQUE INDEX [UX_UserDevices_User_DeviceKeyHash]
            ON [auth].[UserDevices] ([UserId], [DeviceKeyHash])
            WHERE [DeviceKeyHash] IS NOT NULL;
    END;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.indexes
        WHERE [object_id] = OBJECT_ID(N'[auth].[UserDevices]')
          AND [name] = N'IX_UserDevices_User_LastSeenAt'
    )
    BEGIN
        CREATE INDEX [IX_UserDevices_User_LastSeenAt]
            ON [auth].[UserDevices] ([UserId], [LastSeenAt] DESC)
            INCLUDE ([DeviceName], [IsTrusted], [IsRevoked]);
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;
GO

SELECT
    [SchemaName] = SCHEMA_NAME([schema_id]),
    [TableName] = [name]
FROM sys.tables
WHERE [schema_id] = SCHEMA_ID(N'auth')
ORDER BY [name];
GO
