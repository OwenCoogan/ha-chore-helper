"""Module for managing chore sensors in Home Assistant."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    ATTR_HIDDEN,
    CONF_NAME,
)
from homeassistant.helpers.restore_state import RestoreEntity

from . import const, helpers
from .const import LOGGER
from .calendar import EntitiesCalendarData

PLATFORMS: list[str] = [const.CALENDAR_PLATFORM]


class Chore(RestoreEntity):
    """Chore Sensor class."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Chore class."""
        config = config_entry.options
        self.config_entry = config_entry
        self._attr_name = config_entry.title or config.get(CONF_NAME)
        self._hidden = config.get(ATTR_HIDDEN, False)
        self._manual = config.get(const.CONF_MANUAL)

        # Initialize month ranges
        self._first_month = self._get_month(config.get(const.CONF_FIRST_MONTH, const.DEFAULT_FIRST_MONTH))
        self._last_month = self._get_month(config.get(const.CONF_LAST_MONTH, const.DEFAULT_LAST_MONTH))

        # Icons and other settings
        self._initialize_icons(config)
        self._initialize_dates(config)
        self._initialize_attributes()

        # Start date setup
        self._start_date = self._get_start_date(config.get(const.CONF_START_DATE))

    def _get_month(self, month_name: str) -> int:
        """Get the integer value of the month from its name."""
        months = [m["value"] for m in const.MONTH_OPTIONS]
        return months.index(month_name) + 1 if month_name in months else 1

    def _initialize_icons(self, config: dict[str, Any]) -> None:
        """Initialize icons from configuration."""
        self._icon_normal = config.get(const.CONF_ICON_NORMAL)
        self._icon_today = config.get(const.CONF_ICON_TODAY)
        self._icon_tomorrow = config.get(const.CONF_ICON_TOMORROW)
        self._icon_overdue = config.get(const.CONF_ICON_OVERDUE)

    def _initialize_dates(self, config: dict[str, Any]) -> None:
        """Initialize various date-related attributes."""
        self._date_format = config.get(const.CONF_DATE_FORMAT, const.DEFAULT_DATE_FORMAT)
        self._forecast_dates = config.get(const.CONF_FORECAST_DATES, 0)
        self.show_overdue_today = config.get(const.CONF_SHOW_OVERDUE_TODAY, False)
        self._offset_dates = config.get(const.ATTR_OFFSET_DATES, "")
        self._add_dates = config.get(const.ATTR_ADD_DATES, "")
        self._remove_dates = config.get(const.ATTR_REMOVE_DATES, "")

    def _initialize_attributes(self) -> None:
        """Initialize other core attributes."""
        self._due_dates: list[date] = []
        self._next_due_date: date | None = None
        self._last_updated: datetime | None = None
        self.last_completed: datetime | None = None
        self._days: int | None = None
        self._overdue: bool = False
        self._overdue_days: int | None = None
        self._frequency: str = ""
        self._attr_state = self._days
        self._attr_icon = self._icon_normal
        self._user: str | None = None

    def _get_start_date(self, start_date_str: str | None) -> date | None:
        """Convert string to a date, handle invalid values."""
        try:
            return helpers.to_date(start_date_str)
        except ValueError:
            return None

    async def async_added_to_hass(self) -> None:
        """When sensor is added to HA, restore state and add it to calendar."""
        await super().async_added_to_hass()
        await self._restore_state()
        await self._add_to_calendar()

    async def async_will_remove_from_hass(self) -> None:
        """When sensor is removed from HA, remove it and its calendar entity."""
        await super().async_will_remove_from_hass()
        self._remove_from_registry()
        self._remove_from_calendar()

    async def _restore_state(self) -> None:
        """Restore state from the last known state."""
        state = await self.async_get_last_state()  # Await the coroutine
        if not state:
            return
        self._attr_state = state.state
        self._last_updated = None  # Unblock update after options change
        self._days = state.attributes.get(const.ATTR_DAYS)
        self._next_due_date = helpers.parse_optional_date(state.attributes, const.ATTR_NEXT_DATE)
        self.last_completed = helpers.parse_optional_datetime(state.attributes, const.ATTR_LAST_COMPLETED)
        self._overdue = state.attributes.get(const.ATTR_OVERDUE, False)
        self._overdue_days = state.attributes.get(const.ATTR_OVERDUE_DAYS)
        self._offset_dates = state.attributes.get(const.ATTR_OFFSET_DATES, "")
        self._add_dates = state.attributes.get(const.ATTR_ADD_DATES, "")
        self._remove_dates = state.attributes.get(const.ATTR_REMOVE_DATES, "")

    async def _add_to_calendar(self) -> None:
        """Add the chore to the calendar platform."""
        if not self.hidden:
            self._create_calendar_if_needed()
            self.hass.data[const.DOMAIN][const.CALENDAR_PLATFORM].add_entity(self.entity_id)

    async def _remove_from_calendar(self) -> None:
        """Remove the chore from the calendar platform."""
        self.hass.data[const.DOMAIN][const.CALENDAR_PLATFORM].remove_entity(self.entity_id)

    def _create_calendar_if_needed(self) -> None:
        """Create a calendar if not already present."""
        if const.CALENDAR_PLATFORM not in self.hass.data[const.DOMAIN]:
            self.hass.data[const.DOMAIN][const.CALENDAR_PLATFORM] = EntitiesCalendarData(self.hass)
            LOGGER.debug("Creating chore calendar")
            self.hass.config_entries.async_forward_entry_setups(self.config_entry, PLATFORMS)

    def _remove_from_registry(self) -> None:
        """Remove the entity from the platform registry."""
        del self.hass.data[const.DOMAIN][const.SENSOR_PLATFORM][self.entity_id]

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def next_due_date(self) -> date | None:
        """Return next due date."""
        return self._next_due_date

    @property
    def overdue(self) -> bool:
        """Return whether the chore is overdue."""
        return self._overdue

    @property
    def overdue_days(self) -> int | None:
        """Return the number of overdue days."""
        return self._overdue_days

    @property
    def offset_dates(self) -> str:
        """Return offset dates."""
        return self._offset_dates

    @property
    def add_dates(self) -> str:
        """Return additional dates."""
        return self._add_dates

    @property
    def remove_dates(self) -> str:
        """Return removal dates."""
        return self._remove_dates

    @property
    def hidden(self) -> bool:
        """Return whether the entity is hidden."""
        return self._hidden

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement (days)."""
        return "day" if self._days == 1 else "days"

    @property
    def native_value(self) -> object:
        """Return the state of the sensor."""
        return self._attr_state

    @property
    def last_updated(self) -> datetime | None:
        """Return the last updated time."""
        return self._last_updated

    @property
    def icon(self) -> str:
        """Return the entity icon."""
        return self._attr_icon

    @property
    def user(self) -> str:
        """Return the user assigned to this chore."""
        return self._user

    def assign_user(self, user: str) -> None:
        """Assign a user to this chore."""
        self._user = user
        self.update_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            const.ATTR_LAST_COMPLETED: self.last_completed,
            const.ATTR_LAST_UPDATED: self.last_updated,
            const.ATTR_OVERDUE: self.overdue,
            const.ATTR_OVERDUE_DAYS: self.overdue_days,
            const.ATTR_NEXT_DATE: self.next_due_date,
            const.ATTR_OFFSET_DATES: self.offset_dates,
            const.ATTR_ADD_DATES: self.add_dates,
            const.ATTR_REMOVE_DATES: self.remove_dates,
            ATTR_UNIT_OF_MEASUREMENT: self.native_unit_of_measurement,
            ATTR_DEVICE_CLASS: const.DEVICE_CLASS_CHORE,
            ATTR_HIDDEN: self.hidden,
        }

    def update_state(self) -> None:
        """Force a state update."""
        self.async_write_ha_state()
        self._last_updated = datetime.now()

    def set_chore_completed(self, completed_at: datetime | None = None) -> None:
        """Mark the chore as completed."""
        self.last_completed = completed_at or datetime.now()
        LOGGER.debug("Chore '%s' completed at %s", self._attr_name, self.last_completed)
        self.update_state()

    def mark_overdue(self, overdue: bool, overdue_days: int) -> None:
        """Mark the chore as overdue."""
        self._overdue = overdue
        self._overdue_days = overdue_days
        LOGGER.debug("Chore '%s' marked as overdue (%d days)", self._attr_name, self._overdue_days)
        self.update_state()

    def calculate_next_due_date(self) -> None:
        """Calculate and update the next due date."""
        self._next_due_date = helpers.calculate_next_due_date(self._frequency, self.last_completed)
        LOGGER.debug("Next due date for '%s' calculated: %s", self._attr_name, self._next_due_date)
        self.update_state()
