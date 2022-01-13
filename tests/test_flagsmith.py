import json
import uuid

import pytest
import requests
import responses
from flag_engine.features.models import FeatureStateModel, FeatureModel

from flagsmith import Flagsmith
from flagsmith.exceptions import FlagsmithAPIError


def test_flagsmith_starts_polling_manager_on_init_if_enabled(mocker, api_key):
    # Given
    mock_polling_manager = mocker.MagicMock()
    mocker.patch(
        "flagsmith.flagsmith.EnvironmentDataPollingManager",
        return_value=mock_polling_manager,
    )

    # When
    Flagsmith(environment_key=api_key, enable_client_side_evaluation=True)

    # Then
    mock_polling_manager.start.assert_called_once()


@responses.activate()
def test_update_environment_sets_environment(
    flagsmith, environment_json, environment_model
):
    # Given
    responses.add(method="GET", url=flagsmith.environment_url, body=environment_json)
    assert flagsmith._environment is None

    # When
    flagsmith.update_environment()

    # Then
    assert flagsmith._environment is not None
    assert flagsmith._environment == environment_model


@responses.activate()
def test_get_environment_flags_calls_api_when_no_local_environment(
    api_key, flagsmith, flags_json
):
    # Given
    responses.add(method="GET", url=flagsmith.environment_flags_url, body=flags_json)

    # When
    all_flags = flagsmith.get_environment_flags().all_flags()

    # Then
    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["X-Environment-Key"] == api_key

    # Taken from hard coded values in tests/data/flags.json
    assert all_flags[0].enabled is True
    assert all_flags[0].value == "some-value"
    assert all_flags[0].feature_name == "some_feature"


@responses.activate()
def test_get_environment_flags_uses_local_environment_when_available(
    flagsmith, environment_model
):
    # Given
    flagsmith._environment = environment_model

    # When
    all_flags = flagsmith.get_environment_flags().all_flags()

    # Then
    assert len(responses.calls) == 0
    assert len(all_flags) == 1
    assert all_flags[0].feature_name == environment_model.feature_states[0].feature.name
    assert all_flags[0].enabled == environment_model.feature_states[0].enabled
    assert all_flags[0].value == environment_model.feature_states[0].get_value()


@responses.activate()
def test_get_identity_flags_calls_api_when_no_local_environment_no_traits(
    flagsmith, identities_json
):
    # Given
    responses.add(method="POST", url=flagsmith.identities_url, body=identities_json)
    identifier = "identifier"

    # When
    identity_flags = flagsmith.get_identity_flags(identifier=identifier).all_flags()

    # Then
    assert responses.calls[0].request.body.decode() == json.dumps(
        {"identifier": identifier, "traits": []}
    )

    # Taken from hard coded values in tests/data/identities.json
    assert identity_flags[0].enabled is True
    assert identity_flags[0].value == "some-value"
    assert identity_flags[0].feature_name == "some_feature"


@responses.activate()
def test_get_identity_flags_calls_api_when_no_local_environment_no_traits(
    flagsmith, identities_json
):
    # Given
    responses.add(method="POST", url=flagsmith.identities_url, body=identities_json)
    identifier = "identifier"
    traits = {"some_trait": "some_value"}

    # When
    identity_flags = flagsmith.get_identity_flags(identifier=identifier, traits=traits)

    # Then
    assert responses.calls[0].request.body.decode() == json.dumps(
        {
            "identifier": identifier,
            "traits": [{"trait_key": k, "trait_value": v} for k, v in traits.items()],
        }
    )

    # Taken from hard coded values in tests/data/identities.json
    assert identity_flags.all_flags()[0].enabled is True
    assert identity_flags.all_flags()[0].value == "some-value"
    assert identity_flags.all_flags()[0].feature_name == "some_feature"


@responses.activate()
def test_get_identity_flags_uses_local_environment_when_available(
    flagsmith, environment_model, mocker
):
    # Given
    flagsmith._environment = environment_model
    mock_engine = mocker.patch("flagsmith.flagsmith.engine")

    feature_state = FeatureStateModel(
        feature=FeatureModel(id=1, name="some_feature", type="STANDARD"),
        enabled=True,
        featurestate_uuid=str(uuid.uuid4()),
    )
    mock_engine.get_identity_feature_states.return_value = [feature_state]

    # When
    identity_flags = flagsmith.get_identity_flags(
        "identifier", traits={"some_trait": "some_value"}
    ).all_flags()

    # Then
    mock_engine.get_identity_feature_states.assert_called_once()
    assert identity_flags[0].enabled is feature_state.enabled
    assert identity_flags[0].value == feature_state.get_value()


def test_request_connection_error_raises_flagsmith_api_error(mocker, api_key):
    """
    Test the behaviour when session.<method> raises a ConnectionError. Note that this
    does not account for the fact that we are using retries. Since this is a standard
    library, we leave this untested. It is assumed that, once the retries are exhausted,
    the requests library raises requests.ConnectionError.
    """

    # Given
    mock_session = mocker.MagicMock()
    mocker.patch("flagsmith.flagsmith.requests.Session", return_value=mock_session)

    flagsmith = Flagsmith(environment_key=api_key)

    mock_session.get.side_effect = requests.ConnectionError

    # When
    with pytest.raises(FlagsmithAPIError):
        flagsmith.get_environment_flags()

    # Then
    # expected exception raised


@responses.activate()
def test_non_200_response_raises_flagsmith_api_error(flagsmith):
    # Given
    responses.add(url=flagsmith.environment_flags_url, method="GET", status=400)

    # When
    with pytest.raises(FlagsmithAPIError):
        flagsmith.get_environment_flags()

    # Then
    # expected exception raised
