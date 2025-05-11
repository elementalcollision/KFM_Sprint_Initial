"""
Unit tests for the VerificationReportGenerator in report_generator.generator.
"""
import unittest
import sys
import os
import json
import tempfile # For creating temporary files/directories for test outputs
from typing import List
from unittest.mock import patch # Import patch directly

# Add the project root to the path so we can import modules from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.verification.report_generator.generator import VerificationReportGenerator
from src.verification.common_types import OverallVerificationResult, VerificationCheckResult

class TestVerificationReportGenerator(unittest.TestCase):
    """Test cases for the VerificationReportGenerator class."""

    def setUp(self):
        """Set up test environment before each test method."""
        # Create a sample OverallVerificationResult for testing
        self.sample_check_results: List[VerificationCheckResult] = [
            VerificationCheckResult(
                check_name="TestCheck1.ExactMatch",
                passed=True,
                component_id="CompA",
                attribute_checked="status",
                expected_value="active",
                actual_value="active",
                message="Component status is active as expected."
            ),
            VerificationCheckResult(
                check_name="TestCheck2.NumericMismatch",
                passed=False,
                component_id="CompB",
                attribute_checked="value",
                expected_value=100,
                actual_value=105,
                message="Value 105 is not 100."
            )
        ]
        self.sample_overall_result = OverallVerificationResult(
            overall_passed=False,
            checks=self.sample_check_results,
            summary="1 error(s) and 0 warning(s) found out of 2 checks.",
            error_count=1,
            warning_count=0
        )
        
        # Create a temporary directory for report outputs during tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_templates_dir = os.path.join(self.temp_dir.name, "templates")
        os.makedirs(self.mock_templates_dir, exist_ok=True)
        
        # --- FIX: Copy actual template content instead of dummy content ---
        actual_template_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), 
            '../../../src/verification/report_generator/templates/report_template.html'
        ))
        temp_template_path = os.path.join(self.mock_templates_dir, "report_template.html")
        
        try:
            with open(actual_template_path, 'r', encoding='utf-8') as src_file:
                template_content = src_file.read()
            with open(temp_template_path, 'w', encoding='utf-8') as dest_file:
                dest_file.write(template_content)
        except FileNotFoundError:
            # Fallback or error if the source template isn't found during test setup
            print(f"Warning: Source template not found at {actual_template_path}. Writing dummy content.")
            with open(temp_template_path, "w") as dest_file:
                 dest_file.write("<html>Error: Source Template Missing</html>")
        # --- End FIX ---

        self.generator = VerificationReportGenerator(self.sample_overall_result, templates_dir=self.mock_templates_dir)

    def tearDown(self):
        """Clean up test environment after each test method."""
        self.temp_dir.cleanup() # Removes the temporary directory and its contents

    def test_to_json_creates_file_and_content_matches(self):
        """Test that to_json() creates a file with the correct JSON content."""
        output_json_path = os.path.join(self.temp_dir.name, "report.json")
        
        self.generator.to_json(output_json_path)
        
        self.assertTrue(os.path.exists(output_json_path), "JSON report file was not created.")
        
        with open(output_json_path, 'r', encoding='utf-8') as f:
            generated_json_data = json.load(f)
            
        # Compare the generated JSON data with the Pydantic model's dictionary representation
        expected_json_data = self.sample_overall_result.model_dump(mode='json') # Get dict compatible with JSON types
        self.assertEqual(generated_json_data, expected_json_data, 
                         "Generated JSON content does not match expected content.")

    def test_to_json_indentation(self):
        """Test that to_json() respects the indent parameter."""
        output_json_path_indented = os.path.join(self.temp_dir.name, "report_indented.json")
        output_json_path_compact = os.path.join(self.temp_dir.name, "report_compact.json")

        # Generate with default indent (2)
        self.generator.to_json(output_json_path_indented)
        with open(output_json_path_indented, 'r', encoding='utf-8') as f:
            content_indented = f.read()
            self.assertIn('\n  "', content_indented, "JSON should be indented by 2 spaces by default.")

        # Generate with indent=None (compact)
        self.generator.to_json(output_json_path_compact, indent=None)
        with open(output_json_path_compact, 'r', encoding='utf-8') as f:
            content_compact = f.read()
            self.assertNotIn('\n  "', content_compact, "JSON should be compact when indent is None.")
            self.assertNotIn('\n    "', content_compact, "JSON should be compact when indent is None.")

    def test_to_json_io_error(self):
        """Test that to_json() raises IOError for an invalid path (e.g., a directory)."""
        # Using the temporary directory itself as output_path should cause an IOError on write
        invalid_output_path = self.temp_dir.name 
        with self.assertRaises(IOError):
            self.generator.to_json(invalid_output_path)
    
    def test_init_type_error(self):
        """Test that __init__ raises TypeError if result is not OverallVerificationResult."""
        with self.assertRaises(TypeError):
            VerificationReportGenerator({"fake_result": True}) # type: ignore

    def test_to_html_creates_file_and_contains_data(self):
        """Test that to_html() creates a file with expected HTML content."""
        output_html_path = os.path.join(self.temp_dir.name, "report.html")
        
        generated_html = self.generator.to_html(output_html_path)
        
        # Check file creation
        self.assertTrue(os.path.exists(output_html_path), "HTML report file was not created.")
        
        # Check basic structure and content
        self.assertIn("<title>Verification Report</title>", generated_html)
        self.assertIn("<h1>Verification Report</h1>", generated_html)
        
        # Check summary rendering (based on sample data)
        self.assertIn("Overall Result: Failed", generated_html)
        self.assertIn("1 error(s) and 0 warning(s) found out of 2 checks.", generated_html)
        self.assertIn('class="summary failed"', generated_html)
        
        # Check detail table rendering (based on sample data)
        self.assertIn("<h2>Detailed Checks</h2>", generated_html)
        self.assertIn("<td><code>TestCheck1.ExactMatch</code></td>", generated_html)
        self.assertIn("<td>Passed</td>", generated_html)
        self.assertIn("<pre>active</pre>", generated_html) # Expected and Actual
        self.assertIn('class="check-row passed"', generated_html)
        
        self.assertIn("<td><code>TestCheck2.NumericMismatch</code></td>", generated_html)
        self.assertIn("<td>Failed</td>", generated_html)
        self.assertIn("<pre>100</pre>", generated_html) # Expected
        self.assertIn("<pre>105</pre>", generated_html) # Actual
        self.assertIn("Value 105 is not 100.", generated_html) # Message
        self.assertIn('class="check-row failed"', generated_html)

    def test_to_html_io_error(self):
        """Test that to_html() raises IOError for an invalid path."""
        invalid_output_path = self.temp_dir.name # Directory path
        with self.assertRaises(IOError):
            self.generator.to_html(invalid_output_path)
            
    def test_to_html_template_not_found(self):
        """Test that to_html() raises an error if the template doesn't exist."""
        output_html_path = os.path.join(self.temp_dir.name, "report.html")
        with self.assertRaises(Exception) as cm: # Jinja raises TemplateNotFound, but Exception is safer catch-all
            self.generator.to_html(output_html_path, template_name="nonexistent_template.html")
        # Check if the exception message contains the template name
        self.assertIn("nonexistent_template.html", str(cm.exception))

    def test_to_pdf_creates_file(self):
        """Test that to_pdf() creates a non-empty PDF file."""
        output_pdf_path = os.path.join(self.temp_dir.name, "report.pdf")
        
        try:
            self.generator.to_pdf(output_pdf_path)
            self.assertTrue(os.path.exists(output_pdf_path), "PDF report file was not created.")
            # Check if the file is non-empty (basic check)
            self.assertGreater(os.path.getsize(output_pdf_path), 0, "PDF file is empty.")
            # Optional: Check for PDF magic bytes
            with open(output_pdf_path, 'rb') as f:
                magic_bytes = f.read(4)
                self.assertEqual(magic_bytes, b'%PDF', "File does not start with PDF magic bytes.")
        except ImportError as e:
            # If WeasyPrint or dependencies are missing on the test runner machine,
            # skip the test instead of failing it.
            if "WeasyPrint" in str(e):
                self.skipTest(f"Skipping PDF test: WeasyPrint or dependencies not installed/found ({e})")
            else:
                raise # Re-raise other import errors

    def test_to_pdf_uses_provided_html(self):
        """Test that to_pdf() uses provided HTML content if available."""
        output_pdf_path = os.path.join(self.temp_dir.name, "report_custom.pdf")
        custom_html = "<html><body><h1>Custom HTML for PDF</h1></body></html>"
        
        try:
            # We don't need to check the *content* of the PDF easily,
            # but we can verify it runs without calling to_html internally
            # by ensuring the method runs without error when passed custom html.
            self.generator.to_pdf(output_pdf_path, html_content=custom_html)
            self.assertTrue(os.path.exists(output_pdf_path))
            self.assertGreater(os.path.getsize(output_pdf_path), 0)
        except ImportError as e:
            if "WeasyPrint" in str(e):
                self.skipTest(f"Skipping PDF test: WeasyPrint or dependencies not installed/found ({e})")
            else:
                raise

    def test_to_pdf_io_error(self):
        """Test that to_pdf() raises IOError for an invalid path."""
        invalid_output_path = self.temp_dir.name # Directory path
        try:
            with self.assertRaises(IOError):
                self.generator.to_pdf(invalid_output_path)
        except ImportError as e:
             if "WeasyPrint" in str(e):
                self.skipTest(f"Skipping PDF test: WeasyPrint or dependencies not installed/found ({e})")
             else:
                raise

    @unittest.skipIf(VerificationReportGenerator(OverallVerificationResult(overall_passed=True, checks=[])).jinja_env is None, "Jinja2 environment not available")
    def test_to_pdf_template_not_found(self):
        """Test that to_pdf() raises error if html template not found (when html_content=None)."""
        output_pdf_path = os.path.join(self.temp_dir.name, "report_template_error.pdf")
        try:
            with self.assertRaises(Exception) as cm:
                self.generator.to_pdf(output_pdf_path, html_template_name="nonexistent_template.html")
            self.assertIn("nonexistent_template.html", str(cm.exception)) # Check for Jinja2's TemplateNotFound
        except ImportError as e:
            if "WeasyPrint" in str(e):
                 self.skipTest(f"Skipping PDF test: WeasyPrint or dependencies not installed/found ({e})")
            else:
                 raise

    # Mock WeasyPrint not being installed
    @patch('src.verification.report_generator.generator.weasyprint', None)
    def test_to_pdf_raises_import_error_if_weasyprint_missing(self):
        """Test that to_pdf() raises ImportError if WeasyPrint is None."""
        output_pdf_path = os.path.join(self.temp_dir.name, "report_import_error.pdf")
        with self.assertRaises(ImportError) as cm:
            self.generator.to_pdf(output_pdf_path)
        self.assertIn("WeasyPrint library not found", str(cm.exception))

if __name__ == '__main__':
    unittest.main() 