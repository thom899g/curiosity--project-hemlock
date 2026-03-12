"""
Firebase Firestore client for Project Hemlock state management.
Implements robust error handling, retry logic, and connection pooling.
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager
import structlog

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import (
    ResourceExhausted,
    ServiceUnavailable,
    DeadlineExceeded,
    InvalidArgument
)

logger = structlog.get_logger(__name__)

class FirestoreClient:
    """
    Thread-safe Firebase Firestore client with connection pooling and retry logic.
    All writes are atomic with optimistic concurrency control.
    """
    
    def __init__(self, service_account_path: str, project_id: str):
        """
        Initialize Firebase Firestore client.
        
        Args:
            service_account_path: Path to Firebase service account JSON file
            project_id: Firebase project ID
            
        Raises:
            FileNotFoundError: If service account file doesn't exist
            ValueError: If Firebase initialization fails
        """
        self.service_account_path = service_account_path
        self.project_id = project_id
        self._client: Optional[google_firestore.Client] = None
        self._initialized = False
        self._connection_pool = {}
        self._retry_attempts = 3
        self._retry_delay = 1.0
        
        self._initialize_firebase()
    
    def _initialize_firebase(self) -> None:
        """Initialize Firebase Admin SDK with error handling."""
        try:
            # Check if Firebase app already exists
            if not firebase_admin._apps:
                # Verify service account file exists
                import os
                if not os.path.exists(self.service_account_path):
                    raise FileNotFoundError(
                        f"Firebase service account file not found: {self.service_account_path}"
                    )
                
                cred = credentials.Certificate(self.service_account_path)
                firebase_admin.initialize_app(cred, {
                    'projectId': self.project_id,
                })
                logger.info("Firebase Admin SDK initialized", project_id=self.project_id)
            
            self._client = firestore.client()
            self._initialized = True
            logger.info("Firestore client initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Firebase", error=str(e), exc_info=True)