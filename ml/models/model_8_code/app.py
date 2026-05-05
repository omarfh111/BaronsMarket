
import gradio as gr
import numpy as np
import os

# Import all classes needed by checkpoints (must be in __main__ namespace)
from ml.models.model_8_code.models.swins import *
from ml.models.model_8_code.models.fph import *
from ml.models.model_8_code.models.dtd import *
from huggingface_hub import hf_hub_download

from ml.models.model_8_code.inference import DTDPredictor

# Initialize predictor
print("Loading  model...")
hf_token = os.environ.get("HF_TOKEN")


model_path = hf_hub_download(
    repo_id="Askhedi/Document_tampering",
    filename="doctamper.pth",
    token=hf_token,
    cache_dir="./model_cache"
)

predictor = DTDPredictor(
    checkpoint_path=model_path,
    device='auto'
)
print("Model loaded!")

def predict_tampering(image, quality=90):
    """
    Predict document tampering

    Args:
        image: Input image (PIL Image or numpy array)
        quality: JPEG compression quality for DCT analysis

    Returns:
        Tuple of (original, mask, heatmap)
    """
    # Save uploaded image temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        if hasattr(image, 'save'):
            image.save(tmp, 'JPEG', quality=95)
        else:
            from PIL import Image
            Image.fromarray(image).save(tmp, 'JPEG', quality=95)
        tmp_path = tmp.name

    try:
        # Run prediction
        result = predictor.predict(tmp_path, quality=quality)

        return (
            result['original'],
            result['mask'],
            result['heatmap']
        )
    finally:
        import os
        os.unlink(tmp_path)

# Create Gradio interface
with gr.Blocks(title="Document Tampering Detection") as demo:
    gr.Markdown("""
    # 🔍 Document Tampering Detection

    Upload a document image to detect forged or tampered regions using Hedi model.

    **How it works:**
    - The model analyzes JPEG compression artifacts 
    - Red regions indicate potential tampering
    - Works best on JPEG images of documents

    """)

    with gr.Row():
        with gr.Column():
            input_image = gr.Image(
                label="Upload Document Image",
                type="pil"
            )

            quality_slider = gr.Slider(
                minimum=75,
                maximum=95,
                value=90,
                step=5,
                label="JPEG Quality for DCT Analysis",
                info="Higher quality = more sensitive detection"
            )

            submit_btn = gr.Button("Detect Tampering", variant="primary")

        with gr.Column():
            with gr.Tab("Heatmap Overlay"):
                output_heatmap = gr.Image(label="Tampering Heatmap")

            with gr.Tab("Binary Mask"):
                output_mask = gr.Image(label="Tampering Mask")

            with gr.Tab("Original"):
                output_original = gr.Image(label="Original Image")

    # Examples
    gr.Examples(
        examples=[
            ["examples/TamperedPaystub.jpg", 90],
        ],
        inputs=[input_image, quality_slider],
        outputs=[output_original, output_mask, output_heatmap],
        fn=predict_tampering,
        cache_examples=False,
    )

    # Event handlers
    submit_btn.click(
        fn=predict_tampering,
        inputs=[input_image, quality_slider],
        outputs=[output_original, output_mask, output_heatmap]
    )

    gr.Markdown("""
    ---
    ### ℹ️ About

    ** Document Tampering Detector** is a deep learning model designed to detect forged text in document images.

    **Features:**
    - Analyzes JPEG compression artifacts using DCT (Discrete Cosine Transform)
    - Detects copy-paste, splicing, and text manipulation
    - Works on scanned documents, photos of documents, and digital documents

    **Limitations:**
    - Requires JPEG images for DCT analysis
    - May produce false positives on low-quality scans
    - Performance varies with JPEG compression quality
    """)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
