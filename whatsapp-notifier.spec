# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for WhatsApp Notifier (Windows/macOS/Linux).

Bundles the Python application as a single-file windowed executable.
The Node.js bridge is included as data files and requires Node.js
to be installed on the target machine (or bundled separately).
"""

import os
from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.build_main import Analysis

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include the bridge directory (JS source + package.json)
        ('bridge', 'bridge'),
        # Include notification templates if they exist
        ('config', 'config'),
        # Include assets (icon, etc.) if they exist
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'src',
        'src.models',
        'src.models.appointment',
        'src.models.send_result',
        'src.models.send_history',
        'src.models.settings',
        'src.utils.excel_column_mapper',
        'src.services.phone_normalizer',
        'src.services.settings_store',
        'src.services.excel_reader',
        'src.services.template_renderer',
        'src.services.whatsapp_client',
        'src.services.bridge_manager',
        'src.services.send_worker',
        'src.services.csv_exporter',
        'src.services.history_store',
        'src.ui.main_window',
        'src.ui.results_table',
        'src.ui.qr_dialog',
        'src.ui.settings_dialog',
        'src.ui.history_view',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'pytest_asyncio', 'pytest_qt', 'pytest_httpx'],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WhatsAppNotifier',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed mode (no console window)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Set to 'assets/icon.ico' if available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WhatsAppNotifier',
)
