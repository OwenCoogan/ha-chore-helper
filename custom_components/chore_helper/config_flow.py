"""Adds config flow for Chore Helper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from .const import DOMAIN
from homeassistant import config_entries
from homeassistant.const import ATTR_HIDDEN, CONF_NAME
from homeassistant.auth import async_get_users
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
)
from . import const, helpers


async def get_user_options(hass):
    """Fetch user options for the selector."""
    users = await async_get_users(hass)
    return [
        {"value": user.id, "label": user.name}
        for user in users
    ]


async def get_person_entities(hass):
    """Return a dictionary of valid person entity IDs and their names."""
    persons = hass.states.async_all('person')  # Fetch all entities in the 'person' domain
    return {person.entity_id: person.name for person in persons}


async def _validate_config(
    _: SchemaConfigFlowHandler | SchemaOptionsFlowHandler, data: Any
) -> Any:
    """Validate config."""
    # Validate day of the month
    if const.CONF_DAY_OF_MONTH in data and data[const.CONF_DAY_OF_MONTH] < 1:
        data[const.CONF_DAY_OF_MONTH] = None

    # Validate the date field
    if const.CONF_DATE in data:
        if (
            data[const.CONF_DATE] == "0"
            or data[const.CONF_DATE] == "0/0"
            or data[const.CONF_DATE] == ""
        ):
            data[const.CONF_DATE] = None
        else:
            try:
                helpers.month_day_text(data[const.CONF_DATE])
            except vol.Invalid as exc:
                raise SchemaFlowError("month_day") from exc

    # Validate weekday order number
    if (
        const.CONF_WEEKDAY_ORDER_NUMBER in data
        and int(data[const.CONF_WEEKDAY_ORDER_NUMBER]) == 0
    ):
        data[const.CONF_WEEKDAY_ORDER_NUMBER] = None

    # Validate chore day
    if const.CONF_CHORE_DAY in data and data[const.CONF_CHORE_DAY] == "0":
        data[const.CONF_CHORE_DAY] = None

    # Ensure the selected user is valid
    if const.CONF_USER in data:
        user_id = data[const.CONF_USER]
        # Additional validation can be added here if necessary
        data[const.CONF_USER] = user_id  # Store the user ID

    return data


def required(
    key: str, options: dict[str, Any], default: Any | None = None
) -> vol.Required:
    """Return vol.Required."""
    if isinstance(options, dict) and key in options:
        suggested_value = options[key]
    elif default is not None:
        suggested_value = default
    else:
        return vol.Required(key)
    return vol.Required(key, description={"suggested_value": suggested_value})


def optional(
    key: str, options: dict[str, Any], default: Any | None = None
) -> vol.Optional:
    """Return vol.Optional."""
    if isinstance(options, dict) and key in options:
        suggested_value = options[key]
    elif default is not None:
        suggested_value = default
    else:
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": suggested_value})


def general_schema_definition(
    handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler,
) -> Mapping[str, Any]:
    """Create general schema."""
    user_options = handler.hass.loop.run_until_complete(get_user_options(handler.hass))
    schema = {
        required(
            const.CONF_FREQUENCY, handler.options, const.DEFAULT_FREQUENCY
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=const.FREQUENCY_OPTIONS)
        ),
        optional(
            const.CONF_ICON_NORMAL, handler.options, const.DEFAULT_ICON_NORMAL
        ): selector.IconSelector(),
        optional(
            const.CONF_ICON_TOMORROW, handler.options, const.DEFAULT_ICON_TOMORROW
        ): selector.IconSelector(),
        optional(
            const.CONF_ICON_TODAY, handler.options, const.DEFAULT_ICON_TODAY
        ): selector.IconSelector(),
        optional(
            const.CONF_ICON_OVERDUE, handler.options, const.DEFAULT_ICON_OVERDUE
        ): selector.IconSelector(),
        optional(
            const.CONF_FORECAST_DATES, handler.options, const.DEFAULT_FORECAST_DATES
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=100,
                mode=selector.NumberSelectorMode.BOX,
                step=1,
            )
        ),
        optional(ATTR_HIDDEN, handler.options, False): bool,
        optional(const.CONF_MANUAL, handler.options, False): bool,
        optional(
            const.CONF_SHOW_OVERDUE_TODAY,
            handler.options,
            const.DEFAULT_SHOW_OVERDUE_TODAY,
        ): bool,
        optional(
            const.CONF_USER, handler.options
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=user_options)
        ),
        optional(
            const.CONF_PERSON, handler.options
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=await get_person_entities(handler.hass))
        ),
    }

    return schema


async def general_config_schema(
    handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler,
) -> vol.Schema:
    """Generate config schema."""
    schema_obj = {required(CONF_NAME, handler.options): selector.TextSelector()}
    schema_obj.update(general_schema_definition(handler))
    return vol.Schema(schema_obj)


async def general_options_schema(
    handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler,
) -> vol.Schema:
    """Generate options schema."""
    return vol.Schema(general_schema_definition(handler))


async def detail_config_schema(
    handler: SchemaConfigFlowHandler | SchemaOptionsFlowHandler,
) -> vol.Schema:
    """Generate options schema."""
    options_schema: dict[vol.Optional | vol.Required, Any] = {}
    frequency = handler.options.get(const.CONF_FREQUENCY)

    if frequency not in const.BLANK_FREQUENCY:
        if frequency in (
            const.DAILY_FREQUENCY
            + const.WEEKLY_FREQUENCY
            + const.MONTHLY_FREQUENCY
            + const.YEARLY_FREQUENCY
        ):
            uom = {
                "every-n-days": "day(s)",
                "every-n-weeks": "week(s)",
                "every-n-months": "month(s)",
                "every-n-years": "year(s)",
                "after-n-days": "day(s)",
                "after-n-weeks": "week(s)",
                "after-n-months": "month(s)",
                "after-n-years": "year(s)",
            }
            options_schema[required(const.CONF_PERIOD, handler.options)] = (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=1000,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement=uom[frequency],
                    )
                )
            )

        if frequency in const.YEARLY_FREQUENCY:
            options_schema[optional(const.CONF_DATE, handler.options)] = (
                selector.TextSelector()
            )

        if frequency in const.MONTHLY_FREQUENCY:
            options_schema[optional(const.CONF_DAY_OF_MONTH, handler.options)] = (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=31,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                )
            )

            options_schema[
                optional(const.CONF_WEEKDAY_ORDER_NUMBER, handler.options)
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=const.ORDER_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

            options_schema[optional(const.CONF_FORCE_WEEK_NUMBERS, handler.options)] = (
                selector.BooleanSelector()
            )

            options_schema[optional(const.CONF_DUE_DATE_OFFSET, handler.options)] = (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-7,
                        max=7,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="day(s)",
                    )
                )
            )

        if frequency in (const.WEEKLY_FREQUENCY + const.MONTHLY_FREQUENCY):
            options_schema[optional(const.CONF_CHORE_DAY, handler.options)] = (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=const.WEEKDAY_OPTIONS,
                    )
                )
            )

        if frequency in const.WEEKLY_FREQUENCY:
            options_schema[
                required(
                    const.CONF_FIRST_WEEK, handler.options, const.DEFAULT_FIRST_WEEK
                )
            ] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=52,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="weeks",
                )
            )

        if frequency not in const.YEARLY_FREQUENCY:
            options_schema[
                optional(
                    const.CONF_FIRST_MONTH, handler.options, const.DEFAULT_FIRST_MONTH
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(options=const.MONTH_OPTIONS)
            )
            options_schema[
                optional(
                    const.CONF_LAST_MONTH, handler.options, const.DEFAULT_LAST_MONTH
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(options=const.MONTH_OPTIONS)
            )

        options_schema[
            required(const.CONF_START_DATE, handler.options, helpers.now().date())
        ] = selector.DateSelector()

    return vol.Schema(options_schema)


async def choose_details_step(_: dict[str, Any]) -> str:
    """Return next step_id for options flow."""
    return "detail"


CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(general_config_schema, next_step=choose_details_step),
    "detail": SchemaFlowFormStep(
        detail_config_schema, validate_user_input=_validate_config
    ),
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(general_options_schema, next_step=choose_details_step),
    "detail": SchemaFlowFormStep(
        detail_config_schema, validate_user_input=_validate_config
    ),
}

# mypy: ignore-errors
class ChoreHelperConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config or options flow for Chore Helper."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    VERSION = const.CONFIG_VERSION

    async def async_step_user(self, user_input: dict[str, Any] = None) -> dict[str, Any]:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user")

        # Process user input and create a config entry
        return self.async_create_entry(title="Chore Helper", data=user_input)

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title.

        The options parameter contains config entry options, which is the union of user
        input from the config flow steps.
        """
        title = options.get(CONF_NAME, "")
        user = options.get(const.CONF_USER, "Unknown user")
        return f"{title} (Assigned to {user})"
