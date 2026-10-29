from fastapi import APIRouter, status

from goalpost.api.deps import RegistryDep, SessionDep
from goalpost.schemas.connectors import (
    ConnectorCreate,
    ConnectorRead,
    ConnectorsResponse,
    ConnectorTestResult,
    ConnectorTypesResponse,
)
from goalpost.services import connectors

router = APIRouter(tags=["connectors"])


@router.get(
    "/connector-types", response_model=ConnectorTypesResponse, operation_id="getConnectorTypes"
)
def get_connector_types(registry: RegistryDep) -> ConnectorTypesResponse:
    """Installed connectors: config schema, secrets needed, event kinds and rule fields."""
    return connectors.connector_types_view(registry, connectors.read_env())


@router.get("/connectors", response_model=ConnectorsResponse, operation_id="getConnectors")
def get_connectors(session: SessionDep) -> ConnectorsResponse:
    """Your connector instances with status and last sync."""
    return ConnectorsResponse(items=connectors.connectors_view(session))


@router.post(
    "/connectors",
    response_model=ConnectorRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createConnector",
)
def create_connector(
    body: ConnectorCreate, session: SessionDep, registry: RegistryDep
) -> ConnectorRead:
    """Add an instance of an installed connector type. Secrets stay in .env."""
    row = connectors.create_connector(session, registry, body)
    session.commit()
    return connectors.connector_read(session, row)


@router.post(
    "/connectors/{connector_id}/test",
    response_model=ConnectorTestResult,
    operation_id="testConnector",
)
def test_connector(
    connector_id: str, session: SessionDep, registry: RegistryDep
) -> ConnectorTestResult:
    """Run the connector's connection test. A failure is a normal result, not an error."""
    row = connectors.get_connector(session, connector_id)
    result = connectors.test_connector(row, registry, connectors.read_env())
    session.commit()
    return result
