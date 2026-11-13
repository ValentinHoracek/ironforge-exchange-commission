"""Azure Blob / ADLS Gen2 storage, authenticated with Entra ID (account keys are disabled)."""

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from ifec_ingest.storage import AlreadyExists


class AzureBlobStorage:
    """DefaultAzureCredential picks the identity automatically:
    in Azure the job's user-assigned managed identity (selected by AZURE_CLIENT_ID),
    on a laptop the `az login` session. No keys or connection strings anywhere.
    """

    def __init__(self, account_url: str) -> None:
        self._service = BlobServiceClient(account_url, credential=DefaultAzureCredential())

    def read(self, container: str, path: str) -> bytes | None:
        try:
            return self._service.get_blob_client(container, path).download_blob().readall()
        except ResourceNotFoundError:
            return None

    def write(self, container: str, path: str, data: bytes, *, overwrite: bool) -> None:
        # overwrite=False sends "If-None-Match: *": the service refuses to replace an existing blob.
        try:
            self._service.get_blob_client(container, path).upload_blob(data, overwrite=overwrite)
        except ResourceExistsError as exc:
            raise AlreadyExists(f"{container}/{path}") from exc
