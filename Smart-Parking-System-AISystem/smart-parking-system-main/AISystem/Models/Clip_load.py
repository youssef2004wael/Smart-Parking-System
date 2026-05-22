from transformers import CLIPModel, CLIPProcessor

model_id = "openai/clip-vit-base-patch32"

# Download
model = CLIPModel.from_pretrained(model_id)
processor = CLIPProcessor.from_pretrained(model_id)

# Save to a local directory
model.save_pretrained("./clip_local")
processor.save_pretrained("./clip_local")

print("CLIP saved locally to './clip_local'")