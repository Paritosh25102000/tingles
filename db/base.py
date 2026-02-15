"""
Abstract base class for database operations.
Defines the interface that all database adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple
import pandas as pd


class DatabaseAdapter(ABC):
    """Abstract base class for database operations."""

    # ============ PROFILE OPERATIONS ============

    @abstractmethod
    def load_profiles(self, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        Load all profiles from the database.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            DataFrame with all profiles, or None on error
        """
        pass

    @abstractmethod
    def get_profile_by_email(self, email: str, force_refresh: bool = False) -> Optional[Dict]:
        """
        Get a single profile by email address.

        Args:
            email: User's email address
            force_refresh: If True, bypass cache

        Returns:
            Dictionary with profile data (PascalCase keys), or None if not found
        """
        pass

    @abstractmethod
    def add_profile(self, profile_data: Dict) -> bool:
        """
        Add a new profile to the database.

        Args:
            profile_data: Dictionary with profile fields (PascalCase keys)

        Returns:
            True on success, False on failure
        """
        pass

    @abstractmethod
    def update_profile_by_email(self, email: str, updates: Dict) -> bool:
        """
        Update specific fields of a profile.

        Args:
            email: User's email address
            updates: Dictionary with fields to update (PascalCase keys)

        Returns:
            True on success, False on failure
        """
        pass

    # ============ CREDENTIAL OPERATIONS ============

    @abstractmethod
    def load_credentials(self) -> Optional[pd.DataFrame]:
        """
        Load all credentials from the database.

        Returns:
            DataFrame with columns: email, password, role
            Or None on error
        """
        pass

    @abstractmethod
    def add_credential(self, email: str, password: str, role: str = "user") -> Tuple[bool, Optional[str]]:
        """
        Add a new credential (user account).

        Args:
            email: User's email address
            password: User's password (plaintext for now)
            role: User role ("user" or "founder")

        Returns:
            Tuple of (success: bool, error_msg: Optional[str])
        """
        pass

    @abstractmethod
    def authenticate_user(self, email: str, password: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Authenticate a user login attempt.

        Args:
            email: User's email address
            password: User's password

        Returns:
            Tuple of (success: bool, role: Optional[str], error_msg: Optional[str])
        """
        pass

    # ============ SUGGESTION OPERATIONS ============

    @abstractmethod
    def load_suggestions(self) -> Optional[pd.DataFrame]:
        """
        Load all suggestions from the database.

        Returns:
            DataFrame with columns: Suggested_To_Email, Profile_Of_Email, Status
            Or None on error
        """
        pass

    @abstractmethod
    def get_suggestions_for_user(self, user_email: str) -> pd.DataFrame:
        """
        Get all profiles suggested to a specific user, with suggestion status.

        Args:
            user_email: User's email address

        Returns:
            DataFrame with profile data + SuggestionStatus column
        """
        pass

    @abstractmethod
    def add_suggestion(self, suggested_to_email: str, profile_of_email: str, status: str = "Pending") -> bool:
        """
        Create a new suggestion.

        Args:
            suggested_to_email: Email of user receiving the suggestion
            profile_of_email: Email of profile being suggested
            status: Initial status (default: "Pending")

        Returns:
            True on success, False on failure
        """
        pass

    @abstractmethod
    def update_suggestion_status(self, suggested_to_email: str, profile_of_email: str, new_status: str) -> bool:
        """
        Update the status of an existing suggestion.

        Args:
            suggested_to_email: Email of user who received suggestion
            profile_of_email: Email of suggested profile
            new_status: New status value (e.g., "Liked", "Match", "Date", "Married")

        Returns:
            True on success, False on failure
        """
        pass

    @abstractmethod
    def suggestion_exists(self, suggested_to_email: str, profile_of_email: str) -> bool:
        """
        Check if a suggestion already exists.

        Args:
            suggested_to_email: Email of user who received suggestion
            profile_of_email: Email of suggested profile

        Returns:
            True if suggestion exists, False otherwise
        """
        pass
