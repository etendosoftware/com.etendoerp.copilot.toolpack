from copilot.baseutils.logging_envvar import read_optional_env_var
from copilot.core.tool_wrapper import ToolWrapper
from copilot.core.tool_input import ToolInput, ToolField
from typing import Type, List, Final
import base64
import pandas as pd
from langsmith import traceable

class ExcelOCRToolInput(ToolInput):
    path: str = ToolField(description="Path to the Excel file (xls/xlsx/csv)")
    question: str = ToolField(description="Precise instruction on what to extract from the file content.")

GET_JSON_PROMPT: Final[str] = """Extract all useful information from the Excel file as a structured JSON. Don't summarize or omit rows."""

class ExcelOCRTool(ToolWrapper):
    name: str = "ExcelOCRTool"
    description: str = "Extract structured data from Excel using OCR + Vision model."
    args_schema: Type[ToolInput] = ExcelOCRToolInput

    @traceable
    def run(self, input_params, *args, **kwargs):
        output_images = []
        try:
            file_path = input_params["path"]
            question = input_params.get("question", GET_JSON_PROMPT)
            mime_type = "image/jpeg"
            output_images = self.render_excel_to_images(file_path)
            base64_images = [self.image_to_base64(p) for p in output_images]

            messages = [{"role": "user", "content": [
                *[{"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}", "detail": "high"}} for b64 in base64_images],
                {"type": "text", "text": question}
            ]}]

            from langchain_openai import ChatOpenAI
            model = read_optional_env_var("COPILOT_OCRTOOL_MODEL", "gpt-4.1")
            llm = ChatOpenAI(model=model, temperature=0)
            response = llm.invoke(messages)
            return response.content

        except Exception as e:
            return {"error": str(e)}
        finally:
            # Clean up temporary image files
            import os
            for img_path in output_images:
                try:
                    if os.path.exists(img_path):
                        os.unlink(img_path)
                except OSError:
                    pass  # Ignore cleanup errors

    def render_excel_to_images(self, file_path) -> List[str]:
        """
        Renders each sheet of the Excel file to a JPEG image.
        Returns list of file paths to the generated images.
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import tempfile
        import os

        temp_images = []
        xls = pd.ExcelFile(file_path)

        for idx, sheet in enumerate(xls.sheet_names):
            df = pd.read_excel(xls, sheet_name=sheet)
            fig, ax = plt.subplots(figsize=(12, len(df) * 0.3 + 1))
            ax.axis('off')
            tbl = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='left')
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(8)
            # Create a secure temporary file with proper permissions
            temp_fd, img_path = tempfile.mkstemp(suffix=".jpeg", prefix=f"sheet_{idx}_")
            os.close(temp_fd)
            temp_images.append(img_path)
            plt.savefig(img_path, bbox_inches='tight')
            plt.close(fig)

        return temp_images

    def image_to_base64(self, image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
