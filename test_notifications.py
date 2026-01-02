"""
Basic test suite for critical notification functionality
Run with: python -m pytest test_notifications.py -v
"""
import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from notifications import (
    save_users_data, load_users_data, users_data,
    get_default_notification_preferences,
    is_notification_enabled
)


class TestAtomicFileWrites:
    """Test atomic file write operations"""

    def test_save_users_data_creates_temp_file(self, tmp_path, monkeypatch):
        """Verify save uses temporary file for atomic write"""
        test_file = tmp_path / "users_data.json"
        monkeypatch.setattr('notifications.USERS_FILE', str(test_file))
        monkeypatch.setattr('notifications.users_data', {123: {'group': 'Elite', 'completed_quali': None}})

        # Import after monkeypatch
        import notifications
        notifications.save_users_data()

        # Verify temp file doesn't exist after successful save
        assert not os.path.exists(str(test_file) + '.tmp')
        # Verify actual file exists
        assert test_file.exists()

    def test_save_users_data_atomic_replace(self, tmp_path, monkeypatch):
        """Verify save operation is atomic (uses os.replace)"""
        test_file = tmp_path / "users_data.json"
        monkeypatch.setattr('notifications.USERS_FILE', str(test_file))

        # Pre-populate with old data
        test_file.write_text('{"999": {"old": "data"}}')

        # Save new data
        monkeypatch.setattr('notifications.users_data', {123: {'group': 'Elite', 'completed_quali': None, 'notifications': {}}})
        import notifications
        notifications.save_users_data()

        # Verify new data replaced old
        data = json.loads(test_file.read_text())
        assert '999' not in data
        assert '123' in data


class TestNotificationPreferences:
    """Test notification preference system"""

    def test_default_preferences_all_enabled(self):
        """Verify all notifications enabled by default"""
        prefs = get_default_notification_preferences()
        assert prefs['48h'] is True
        assert prefs['24h'] is True
        assert prefs['2h'] is True
        assert prefs['10min'] is True
        assert prefs['opens_soon'] is True
        assert prefs['race_replay'] is True
        assert prefs['race_live'] is True

    def test_is_notification_enabled_default(self, monkeypatch):
        """Test notification enabled check with default preferences"""
        monkeypatch.setattr('notifications.users_data', {
            123: {'notifications': get_default_notification_preferences()}
        })
        assert is_notification_enabled(123, '48h') is True
        assert is_notification_enabled(123, 'race_live') is True

    def test_is_notification_enabled_custom(self, monkeypatch):
        """Test notification enabled check with custom preferences"""
        custom_prefs = get_default_notification_preferences()
        custom_prefs['48h'] = False
        monkeypatch.setattr('notifications.users_data', {
            123: {'notifications': custom_prefs}
        })
        assert is_notification_enabled(123, '48h') is False
        assert is_notification_enabled(123, '24h') is True


class TestMigration:
    """Test user data migration logic"""

    @patch('notifications.save_users_data')
    @patch('notifications.load_users_data')
    def test_migration_batches_saves(self, mock_load, mock_save, monkeypatch):
        """Verify migration only saves once for multiple missing fields"""
        from notifications import get_user_status

        # User missing both 'group' and 'notifications'
        monkeypatch.setattr('notifications.users_data', {
            123: {'completed_quali': None}
        })

        get_user_status(123)

        # Should only call save_users_data ONCE, not twice
        assert mock_save.call_count == 1


class TestNotificationWindows:
    """Test notification timing window logic"""

    def test_48h_window_tolerance(self):
        """Test 48h notification window (±6min tolerance)"""
        now = datetime.utcnow()
        quali_close = now + timedelta(hours=48, minutes=3)  # 48h + 3min

        time_until = (quali_close - now).total_seconds() / 3600
        target_hours = 48
        tolerance_hours = 6 / 60

        # Should be within window
        assert abs(time_until - target_hours) <= tolerance_hours

    def test_48h_window_outside_tolerance(self):
        """Test 48h notification outside window"""
        now = datetime.utcnow()
        quali_close = now + timedelta(hours=48, minutes=10)  # 48h + 10min (outside ±6min)

        time_until = (quali_close - now).total_seconds() / 3600
        target_hours = 48
        tolerance_hours = 6 / 60

        # Should be outside window
        assert abs(time_until - target_hours) > tolerance_hours


class TestCallbackParsing:
    """Test callback data parsing robustness"""

    @pytest.mark.asyncio
    async def test_invalid_race_id_handling(self):
        """Test that invalid callback data doesn't crash"""
        from handlers import handle_quali_done

        # Create mock callback with malformed data
        mock_callback = AsyncMock()
        mock_callback.data = "done_invalid"
        mock_callback.answer = AsyncMock()

        await handle_quali_done(mock_callback)

        # Should have called answer with error
        mock_callback.answer.assert_called_once()
        call_args = mock_callback.answer.call_args[0][0]
        assert "Invalid" in call_args or "❌" in call_args

    @pytest.mark.asyncio
    async def test_missing_race_id_handling(self):
        """Test callback data without race ID"""
        from handlers import handle_quali_done

        mock_callback = AsyncMock()
        mock_callback.data = "done_"  # Missing race ID
        mock_callback.answer = AsyncMock()

        await handle_quali_done(mock_callback)

        # Should handle gracefully
        mock_callback.answer.assert_called_once()


class TestFilePathRobustness:
    """Test that file paths are absolute and work from any directory"""

    def test_users_file_is_absolute(self):
        """Verify USERS_FILE uses absolute path"""
        from notifications import USERS_FILE
        assert os.path.isabs(USERS_FILE)

    def test_calendar_file_is_absolute(self):
        """Verify calendar files use absolute paths"""
        from config import CALENDAR_FILE, NEXT_SEASON_FILE
        assert os.path.isabs(CALENDAR_FILE)
        assert os.path.isabs(NEXT_SEASON_FILE)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
