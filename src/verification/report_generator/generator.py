"""
This module will contain the VerificationReportGenerator class 
responsible for generating reports in various formats (HTML, PDF, JSON).
"""

import json
import os
import logging
from typing import Optional, Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound

# Assuming common_types.py is in src/verification/
# This adds src to the Python path to allow imports like from verification.common_types
# import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
# REMOVED sys.path manipulation

from ..common_types import OverallVerificationResult # Use relative import
from src.core.exceptions import ReportingError, ConfigurationError # Added custom exceptions

# Try to import WeasyPrint, but make it an optional dependency for PDF generation
try:
    import weasyprint
except ImportError:
    weasyprint = None # Indicates WeasyPrint is not available

logger = logging.getLogger(__name__) # Added logger

class VerificationReportGenerator:
    """
    Generates verification reports in various formats (JSON, HTML, PDF)
    from an OverallVerificationResult object.
    """

    def __init__(self, result: OverallVerificationResult, templates_dir: Optional[str] = None):
        """
        Initializes the report generator with the verification result.

        Args:
            result: The OverallVerificationResult object containing verification data.
            templates_dir: Path to the directory containing Jinja2 templates.
                           Defaults to 'templates' subdirectory within this module's directory.
        """
        if not isinstance(result, OverallVerificationResult):
            # This is a programming error, not a user config error usually.
            # However, it indicates a misuse of the class.
            msg = "Input 'result' must be an instance of OverallVerificationResult."
            logger.error(msg)
            raise TypeError(msg)
        self.result = result

        if templates_dir is None:
            self.templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        else:
            self.templates_dir = templates_dir
        
        # Check for templates_dir existence early if HTML/PDF might be used.
        # It's a configuration issue if it's needed and not found.
        if not os.path.isdir(self.templates_dir):
            msg = f"Templates directory not found or is not a directory: {self.templates_dir}"
            logger.warning(f"{msg} - HTML/PDF generation might fail.") 
            # We don't raise ConfigurationError here immediately, as JSON might still work.
            # The methods requiring templates will check and raise.

        try:
            self.jinja_env = Environment(
                loader=FileSystemLoader(self.templates_dir),
                autoescape=select_autoescape(['html', 'xml'])
            )
        except Exception as e: # Catch potential errors during Jinja2 Env setup
            msg = f"Failed to initialize Jinja2 environment with templates_dir '{self.templates_dir}': {e}"
            logger.error(msg, exc_info=True)
            raise ConfigurationError(msg) from e

    def _ensure_templates_dir_exists(self):
        """Checks if the templates directory exists and is valid, raises ConfigurationError if not."""
        if not hasattr(self, 'jinja_env') or not self.templates_dir or not os.path.isdir(self.templates_dir):
            msg = f"HTML/PDF report generation requires a valid templates directory. Directory not found or invalid: {self.templates_dir}"
            logger.error(msg)
            raise ConfigurationError(msg)

    def to_json(self, output_path: str, indent: Optional[int] = 2) -> None:
        """
        Generates a JSON report.

        Args:
            output_path: The path where the JSON file will be saved.
            indent: Indentation level for pretty-printing the JSON. Defaults to 2.
        """
        logger.info(f"Generating JSON report to {output_path}")
        try:
            json_output = self.result.model_dump_json(indent=indent)
            os.makedirs(os.path.dirname(output_path), exist_ok=True) # Ensure dir exists
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_output)
            logger.info(f"JSON report successfully generated at {output_path}")
        except IOError as e:
            msg = f"IOError writing JSON report to {output_path}: {e}"
            logger.error(msg, exc_info=True)
            raise ReportingError(msg) from e
        except Exception as e:
            msg = f"Unexpected error during JSON report generation for {output_path}: {e}"
            logger.error(msg, exc_info=True)
            raise ReportingError(msg) from e

    def to_html(self, output_path: str, template_name: str = "report_template.html") -> str:
        """
        Generates an HTML report using a Jinja2 template.
        
        Args:
            output_path: The path where the HTML file will be saved.
            template_name: The name of the Jinja2 template file within the templates directory.
        
        Returns:
            The generated HTML content as a string.
        """
        logger.info(f"Generating HTML report to {output_path} using template {template_name}")
        self._ensure_templates_dir_exists() # Check before trying to use jinja_env
        try:
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(result=self.result)
            os.makedirs(os.path.dirname(output_path), exist_ok=True) # Ensure dir exists
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"HTML report successfully generated at {output_path}")
            return html_content
        except TemplateNotFound as e:
            msg = f"HTML template '{template_name}' not found in {self.templates_dir}: {e}"
            logger.error(msg, exc_info=True)
            raise ConfigurationError(msg) from e # Template not found is a config issue
        except IOError as e:
            msg = f"IOError writing HTML report to {output_path}: {e}"
            logger.error(msg, exc_info=True)
            raise ReportingError(msg) from e
        except Exception as e:
            msg = f"Unexpected error during HTML report generation for {output_path}: {e}"
            logger.error(msg, exc_info=True)
            raise ReportingError(msg) from e

    def to_pdf(self, output_path: str, html_content: Optional[str] = None, html_template_name: str = "report_template.html") -> None:
        """
        Generates a PDF report from HTML content using WeasyPrint.

        Args:
            output_path: The path where the PDF file will be saved.
            html_content: Optional. If provided, this HTML string is used to generate the PDF.
                          If None, to_html() is called first to generate the HTML content.
            html_template_name: The Jinja2 template to use if html_content is None.
        
        Raises:
            ImportError: If the WeasyPrint library is not installed.
            IOError: If the PDF file cannot be written.
            Exception: For errors during HTML generation or PDF conversion.
        """
        logger.info(f"Generating PDF report to {output_path}")
        if weasyprint is None:
            msg = ("WeasyPrint library not found or its system dependencies are missing. "
                   "PDF generation is disabled. Please install correctly (e.g., pip install WeasyPrint and system deps like pango, cairo).")
            logger.error(msg)
            raise ReportingError(msg) # Changed from ImportError to ReportingError for consistency

        self._ensure_templates_dir_exists() # Check before trying to use jinja_env for HTML generation

        html_content_for_pdf: str
        try:
            if html_content is None:
                logger.debug(f"No pre-rendered HTML provided for PDF, generating from template {html_template_name}")
                template = self.jinja_env.get_template(html_template_name)
                html_content_for_pdf = template.render(result=self.result)
            else:
                logger.debug("Using pre-rendered HTML content for PDF generation.")
                html_content_for_pdf = html_content
            
            logger.debug("Converting HTML to PDF using WeasyPrint...")
            # Use a valid existing directory for base_url if needed for relative paths in HTML
            # self.templates_dir should exist due to _ensure_templates_dir_exists()
            pdf_bytes = weasyprint.HTML(string=html_content_for_pdf, base_url=self.templates_dir).write_pdf()
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True) # Ensure dir exists
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            logger.info(f"PDF report successfully generated at {output_path}")

        except TemplateNotFound as e: # If HTML was to be generated
            msg = f"HTML template '{html_template_name}' for PDF generation not found in {self.templates_dir}: {e}"
            logger.error(msg, exc_info=True)
            raise ConfigurationError(msg) from e
        except IOError as e:
            msg = f"IOError writing PDF report to {output_path}: {e}"
            logger.error(msg, exc_info=True)
            raise ReportingError(msg) from e
        except Exception as e: # Catch WeasyPrint errors or other issues
            # WeasyPrint can raise various errors, not always just its own specific ones.
            msg = f"Unexpected error during PDF report generation for {output_path} (possibly WeasyPrint issue): {e}"
            logger.error(msg, exc_info=True)
            raise ReportingError(msg) from e 