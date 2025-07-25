import cv2
import os

# Chemin vers le dossier d’images
image_folder = r'C:\Users\mouri\Pictures\Fractals'
video_name = 'output.mp4'

# Récupère et trie les fichiers dans le dossier
images = sorted([
    img for img in os.listdir(image_folder)
    if img.startswith("frame_") and img.endswith(".jpg")  # ou .jpg selon ton cas
])

# Charge la première image pour obtenir les dimensions
first_frame_path = os.path.join(image_folder, images[0])
frame = cv2.imread(first_frame_path)
height, width, _ = frame.shape

# Initialise l'écriture vidéo (30 fps ici)
video = cv2.VideoWriter(
    os.path.join(image_folder, video_name),
    cv2.VideoWriter_fourcc(*'mp4v'),
    30,
    (width, height)
)

# Ajoute chaque image à la vidéo
for image in images:
    img_path = os.path.join(image_folder, image)
    frame = cv2.imread(img_path)
    video.write(frame)

video.release()
print("✅ Vidéo créée avec succès :", os.path.join(image_folder, video_name))
