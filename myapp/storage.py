"""
Custom storage backends for Arbutus Object Storage with proper content type handling
"""

import mimetypes

from storages.backends.s3boto3 import S3Boto3Storage


class ArbutusMediaStorage(S3Boto3Storage):
    """
    Custom S3Boto3Storage backend for Arbutus Object Storage
    Ensures proper content types are set for uploaded files
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize mimetypes database
        mimetypes.init()

    def get_object_parameters(self, name):
        """
        Override to set proper ContentType based on file extension
        This is called before upload to S3/Arbutus
        """
        params = super().get_object_parameters(name)

        # Get content type from filename
        content_type = self._get_content_type(name)

        # Set ContentType in upload parameters
        if content_type:
            params["ContentType"] = content_type
            # Also set ContentDisposition for better browser handling
            if content_type == "application/pdf":
                # For PDFs, use inline to display in browser
                params["ContentDisposition"] = "inline"
            elif content_type.startswith("image/"):
                # For images, also use inline
                params["ContentDisposition"] = "inline"

        return params

    def _get_content_type(self, name):
        """
        Determine content type from file extension
        Returns the MIME type or None
        """
        # Get content type using mimetypes library
        content_type, _ = mimetypes.guess_type(name)

        if content_type:
            return content_type

        # Fallback for common file types if mimetypes doesn't detect
        extension = name.split(".")[-1].lower()
        fallback_types = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "svg": "image/svg+xml",
            "ico": "image/x-icon",
            "bmp": "image/bmp",
            "tiff": "image/tiff",
            "tif": "image/tiff",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ppt": "application/vnd.ms-powerpoint",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "txt": "text/plain",
            "csv": "text/csv",
            "json": "application/json",
            "xml": "application/xml",
            "zip": "application/zip",
            "tar": "application/x-tar",
            "gz": "application/gzip",
            "mp4": "video/mp4",
            "avi": "video/x-msvideo",
            "mov": "video/quicktime",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
        }

        return fallback_types.get(extension, "application/octet-stream")
