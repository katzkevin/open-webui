from test.util.abstract_integration_test import AbstractPostgresTest
from test.util.mock_user import mock_webui_user


class TestModels(AbstractPostgresTest):
    BASE_PATH = "/api/v1/models"

    @classmethod
    def setup_class(cls):
        super().setup_class()
        from open_webui.models.models import Model

        cls.models = Model

    def test_models(self):
        # Use /list endpoint which queries the database directly
        # Returns {"items": [...], "total": N}
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.get(self.create_url("/list"))
        assert response.status_code == 200
        assert response.json()["total"] == 0

        # Create model via /create endpoint (requires admin)
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.post(
                self.create_url("/create"),
                json={
                    "id": "my-model",
                    "base_model_id": "base-model-id",
                    "name": "Hello World",
                    "meta": {
                        "profile_image_url": "/static/favicon.png",
                        "description": "description",
                        "capabilities": None,
                        "model_config": {},
                    },
                    "params": {},
                },
            )
        assert response.status_code == 200

        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.get(self.create_url("/list"))
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # Get specific model by id
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.get(
                self.create_url("/model"),
                params={"id": "my-model"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "my-model"
        assert data["name"] == "Hello World"

        # Delete model via /model/delete endpoint (requires admin)
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.post(
                self.create_url("/model/delete"),
                json={"id": "my-model"},
            )
        assert response.status_code == 200

        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.get(self.create_url("/list"))
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_bulk_configure_create_models(self):
        """Test bulk-configure creates new model entries with correct field names"""
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [
                        {
                            "id": "test-model-1",
                            "toolIds": ["tool-a", "tool-b"],
                            "defaultFeatureIds": ["tool-a"],
                            "is_active": True,
                        },
                        {
                            "id": "test-model-2",
                            "toolIds": ["tool-c"],
                            "defaultFeatureIds": [],
                            "system_message": "You are a helpful assistant.",
                            "is_active": True,
                        },
                    ],
                    "options": {
                        "create_if_missing": True,
                        "delete_unlisted": False,
                    },
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["summary"]["created"] == 2
        assert data["summary"]["updated"] == 0
        assert data["summary"]["deleted"] == 0

        # Verify the stored field names are snake_case (tool_ids, not toolIds)
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.get(
                self.create_url("/model"),
                params={"id": "test-model-1"},
            )
        assert response.status_code == 200
        model_data = response.json()
        # Backend uses snake_case field names
        assert model_data["meta"]["tool_ids"] == ["tool-a", "tool-b"]
        assert model_data["meta"]["default_feature_ids"] == ["tool-a"]

    def test_bulk_configure_update_models(self):
        """Test bulk-configure updates existing model entries"""
        # First create a model
        with mock_webui_user(id="admin", role="admin"):
            self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [
                        {
                            "id": "test-model-update",
                            "toolIds": ["old-tool"],
                            "is_active": True,
                        }
                    ],
                    "options": {"create_if_missing": True},
                },
            )

        # Now update it
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [
                        {
                            "id": "test-model-update",
                            "toolIds": ["new-tool-a", "new-tool-b"],
                            "defaultFeatureIds": ["new-tool-a"],
                            "is_active": False,
                        }
                    ],
                    "options": {"create_if_missing": False},
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["summary"]["updated"] == 1
        assert data["summary"]["created"] == 0

    def test_bulk_configure_delete_unlisted(self):
        """Test bulk-configure deletes models not in the request when delete_unlisted=True"""
        # Create two models
        with mock_webui_user(id="admin", role="admin"):
            self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [
                        {"id": "model-to-keep", "toolIds": []},
                        {"id": "model-to-delete", "toolIds": []},
                    ],
                    "options": {"create_if_missing": True},
                },
            )

        # Now bulk-configure with only one model and delete_unlisted=True
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [
                        {"id": "model-to-keep", "toolIds": ["updated-tool"]},
                    ],
                    "options": {
                        "create_if_missing": False,
                        "delete_unlisted": True,
                    },
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["summary"]["updated"] == 1
        assert data["summary"]["deleted"] == 1

        # Verify deleted model details
        deleted_details = [d for d in data["details"] if d["action"] == "deleted"]
        assert len(deleted_details) == 1
        assert deleted_details[0]["id"] == "model-to-delete"

    def test_bulk_configure_skip_missing_when_create_disabled(self):
        """Test bulk-configure skips non-existent models when create_if_missing=False"""
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [
                        {"id": "non-existent-model", "toolIds": ["tool-a"]},
                    ],
                    "options": {
                        "create_if_missing": False,
                        "delete_unlisted": False,
                    },
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["summary"]["skipped"] == 1
        assert data["summary"]["created"] == 0

        # Verify skip details
        skipped_details = [d for d in data["details"] if d["action"] == "skipped"]
        assert len(skipped_details) == 1
        assert "create_if_missing=false" in skipped_details[0]["error"]

    def test_bulk_configure_system_message(self):
        """Test bulk-configure sets system message correctly"""
        system_msg = "You are a specialized coding assistant."

        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [
                        {
                            "id": "model-with-system-msg",
                            "toolIds": [],
                            "system_message": system_msg,
                        },
                    ],
                    "options": {"create_if_missing": True},
                },
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify by fetching the model
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.get(
                self.create_url("/model"),
                params={"id": "model-with-system-msg"},
            )
        assert response.status_code == 200
        model_data = response.json()
        assert model_data["meta"]["suggestion_prompts"] == system_msg

    def test_bulk_configure_empty_request(self):
        """Test bulk-configure with empty models list"""
        with mock_webui_user(id="admin", role="admin"):
            response = self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [],
                    "options": {"create_if_missing": True},
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["summary"]["created"] == 0
        assert data["summary"]["updated"] == 0

    def test_bulk_configure_requires_admin(self):
        """Test bulk-configure requires admin role"""
        with mock_webui_user(id="regular-user", role="user"):
            response = self.fast_api_client.post(
                self.create_url("/bulk-configure"),
                json={
                    "models": [{"id": "test", "toolIds": []}],
                },
            )
        # Should be forbidden for non-admin
        assert response.status_code in [401, 403]
