"""PluginVersionResolver and PluginCompatibilityChecker.

Handles semantic version resolution, compatibility checking between
plugins and the application, and dependency requirement matching.
"""
from __future__ import annotations

from packaging.version import InvalidVersion, Version

from backend.infrastructure.plugins.errors import PluginVersionError
from backend.infrastructure.plugins.types import PluginManifest


class PluginVersionResolver:
    """Resolves version constraints for plugin dependencies.

    Supports:
    - Exact version matching
    - Caret ranges (^1.0.0 = >=1.0.0, <2.0.0)
    - Tilde ranges (~1.0.0 = >=1.0.0, <1.1.0)
    - Greater-than/equal ranges (>=1.0.0)
    - Less-than/equal ranges (<=1.0.0)
    """

    @staticmethod
    def satisfies(version: str, constraint: str) -> bool:
        """Check if a version satisfies a constraint string.

        Args:
            version: The version to check (semver).
            constraint: The constraint string (e.g., '>=1.0.0', '^1.0.0').

        Returns:
            True if the version satisfies the constraint.
        """
        try:
            ver = Version(version)
        except InvalidVersion:
            return False

        constraint = constraint.strip()

        if not constraint or constraint == "*":
            return True

        if constraint.startswith(">="):
            try:
                return ver >= Version(constraint[2:])
            except InvalidVersion:
                return False
        elif constraint.startswith(">"):
            try:
                return ver > Version(constraint[1:])
            except InvalidVersion:
                return False
        elif constraint.startswith("<="):
            try:
                return ver <= Version(constraint[2:])
            except InvalidVersion:
                return False
        elif constraint.startswith("<"):
            try:
                return ver < Version(constraint[1:])
            except InvalidVersion:
                return False
        elif constraint.startswith("^"):
            try:
                target = Version(constraint[1:])
                return ver.major == target.major and ver >= target
            except InvalidVersion:
                return False
        elif constraint.startswith("~"):
            try:
                target = Version(constraint[1:])
                return (ver.major == target.major and ver.minor == target.minor and ver >= target)
            except InvalidVersion:
                return False
        elif constraint.startswith("!="):
            try:
                return ver != Version(constraint[2:])
            except InvalidVersion:
                return False
        else:
            try:
                return ver == Version(constraint)
            except InvalidVersion:
                return False

    @staticmethod
    def max_satisfying(versions: list[str], constraint: str) -> str | None:
        """Find the maximum version that satisfies a constraint.

        Args:
            versions: List of available version strings.
            constraint: The constraint string.

        Returns:
            Highest matching version, or None if no match.
        """
        matching: list[Version] = []
        for v in versions:
            try:
                if PluginVersionResolver.satisfies(v, constraint):
                    matching.append(Version(v))
            except InvalidVersion:
                continue

        if not matching:
            return None
        return str(max(matching))

    @staticmethod
    def sort_versions(versions: list[str], reverse: bool = False) -> list[str]:
        """Sort version strings in ascending or descending order.

        Args:
            versions: List of version strings.
            reverse: If True, sort descending.

        Returns:
            Sorted list of version strings.
        """
        parsed: list[tuple[Version, str]] = []
        for v in versions:
            try:
                parsed.append((Version(v), v))
            except InvalidVersion:
                parsed.append((Version("0.0.0"), v))

        parsed.sort(key=lambda x: x[0], reverse=reverse)
        return [v for _, v in parsed]


class PluginCompatibilityChecker:
    """Checks compatibility between plugins and the application.

    Validates:
    - Plugin version compatibility with app version
    - Dependency version satisfaction
    - Platform compatibility
    """

    def __init__(self, app_version: str = "1.0.0") -> None:
        self._app_version = app_version

    @property
    def app_version(self) -> str:
        return self._app_version

    def check_plugin_compatibility(self, manifest: PluginManifest) -> list[str]:
        """Check if a plugin is compatible with the current application.

        Args:
            manifest: Plugin manifest to check.

        Returns:
            List of compatibility issue descriptions (empty if compatible).
        """
        issues: list[str] = []

        # Check app version compatibility
        if not manifest.is_compatible_with_app(self._app_version):
            min_ver = manifest.min_app_version
            max_ver = manifest.max_app_version or "unlimited"
            issues.append(
                f"Plugin version {manifest.version} requires app version "
                f"{min_ver} to {max_ver}, but current is {self._app_version}"
            )

        # Check min_app_version
        try:
            app = Version(self._app_version)
            min_required = Version(manifest.min_app_version)
            if app < min_required:
                issues.append(
                    f"Application version {self._app_version} is below "
                    f"minimum required {manifest.min_app_version}"
                )
        except InvalidVersion:
            issues.append(f"Invalid app version format: {self._app_version}")

        # Check max_app_version
        if manifest.max_app_version:
            try:
                max_allowed = Version(manifest.max_app_version)
                if app > max_allowed:
                    issues.append(
                        f"Application version {self._app_version} exceeds "
                        f"maximum supported {manifest.max_app_version}"
                    )
            except InvalidVersion:
                issues.append(f"Invalid max_app_version format: {manifest.max_app_version}")

        return issues

    def check_dependency_compatibility(
        self,
        manifest: PluginManifest,
        available_plugins: dict[str, PluginManifest],
    ) -> list[str]:
        """Check that all plugin dependencies are available and compatible.

        Args:
            manifest: Plugin manifest whose dependencies to check.
            available_plugins: All available plugins (id -> manifest).

        Returns:
            List of dependency issue descriptions (empty if all satisfied).
        """
        issues: list[str] = []

        for dep in manifest.dependencies:
            if dep.package not in available_plugins:
                issues.append(f"Missing dependency: {dep.package} (required: {dep.version_spec or 'any'})")
                continue

            dep_manifest = available_plugins[dep.package]
            if dep.version_spec and not PluginVersionResolver.satisfies(
                dep_manifest.version, dep.version_spec
            ):
                issues.append(
                    f"Dependency {dep.package} version {dep_manifest.version} "
                    f"does not satisfy constraint '{dep.version_spec}' "
                    f"(required by {manifest.id})"
                )

        return issues

    def is_plugin_compatible(self, manifest: PluginManifest) -> bool:
        """Quick check if a plugin is compatible.

        Args:
            manifest: Plugin manifest to check.

        Returns:
            True if fully compatible.
        """
        return len(self.check_plugin_compatibility(manifest)) == 0
