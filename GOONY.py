import os

folder = os.path.join(os.path.dirname(__file__), "faces_list")

print("Looking here:", folder)
print("Exists:", os.path.exists(folder))

faces = os.listdir(folder)
print(faces)