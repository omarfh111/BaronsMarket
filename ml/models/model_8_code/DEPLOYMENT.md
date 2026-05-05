# 🚀 Deployment Guide - DTD Document Tampering Detection

## Hugging Face Spaces Deployment

### Prerequisites

- Hugging Face account
- Git installed locally
- Git LFS installed (for large model files)

### Step 1: Install Git LFS

```bash
# Mac
brew install git-lfs

# Linux
sudo apt-get install git-lfs

# Initialize Git LFS
git lfs install
```

### Step 2: Create Hugging Face Space

1. Go to https://huggingface.co/new-space
2. Choose a name (e.g., `dtd-doctamper-detection`)
3. Select **Gradio** as SDK
4. Choose license: **MIT**
5. Click **Create Space**

### Step 3: Clone and Setup

```bash
# Clone your new space
git clone https://huggingface.co/spaces/YOUR_USERNAME/dtd-doctamper-detection
cd dtd-doctamper-detection

# Copy app files
cp -r /path/to/gradio_dtd_app/* .

# Track large files with Git LFS
git lfs track "*.pth"
git lfs track "*.pt"
git add .gitattributes

# Add all files
git add .

# Commit
git commit -m "Initial commit: DTD document tampering detection app"

# Push to Hugging Face
git push
```

### Step 4: Configure Space Settings

After pushing, Hugging Face will automatically:
- Install dependencies from `requirements.txt`
- Build the Docker container
- Start the Gradio app
- Assign a public URL

### Step 5: Test Your Space

Visit: `https://huggingface.co/spaces/YOUR_USERNAME/dtd-doctamper-detection`

## Local Testing

Before deploying, test locally:

```bash
cd gradio_dtd_app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run app
python app.py
```

Open browser to: `http://localhost:7860`

## Troubleshooting

### Issue: Git LFS bandwidth limit

**Solution**: Use Hugging Face's built-in LFS storage:

```bash
# Track checkpoint files
git lfs track "checkpoints/*.pth"
git lfs track "checkpoints/*.pt"
git add .gitattributes checkpoints/
git commit -m "Add model checkpoints"
git push
```

### Issue: Build timeout

**Solution**: Reduce requirements versions or use pre-built images:

```yaml
# Create .github/workflows/deploy.yml
sdk: gradio
sdk_version: 4.44.0
python_version: "3.10"
```

### Issue: Out of memory

**Solution**: Enable GPU hardware in Space settings:
1. Go to Space settings
2. Select **Hardware**: GPU (free tier: T4)
3. Save changes

## File Size Optimization

Current app size: **~450MB**

To reduce size:

1. **Quantize models** (reduce precision):
```python
# In inference.py
torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
```

2. **Use model compression**:
```bash
pip install onnx onnxruntime
# Convert to ONNX format (smaller)
```

3. **Lazy loading**:
```python
# Load models on first request instead of startup
@lru_cache()
def get_model():
    return DTDPredictor()
```

## Environment Variables

Add to Space secrets:

```bash
# Optional: Analytics tracking
ANALYTICS_TOKEN=your_token

# Optional: Rate limiting
MAX_REQUESTS_PER_HOUR=100
```

## Monitoring

Check Space logs:
1. Go to Space page
2. Click **Logs** tab
3. Monitor real-time inference

## Custom Domain (Optional)

1. Go to Space settings
2. Add custom domain
3. Configure DNS records

## Cost Optimization

**Free Tier Limits:**
- CPU: Free (slower inference)
- GPU T4: Free tier available
- Storage: 50GB LFS
- Bandwidth: Limited

**Upgrade Options:**
- GPU A10G: Faster inference
- Persistent storage
- Higher bandwidth

## Support

- [Hugging Face Docs](https://huggingface.co/docs/hub/spaces)
- [Gradio Docs](https://gradio.app/docs/)
- [Git LFS](https://git-lfs.github.com/)

## License

MIT License - See LICENSE file
