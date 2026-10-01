import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import pygame
import sys
import os
import urllib.request
import math
import random

# 1. 모델 다운로드
MODEL_PATH = 'face_landmarker.task'
if not os.path.exists(MODEL_PATH):
    print("AI 모델 파일을 다운로드 중입니다...")
    url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    urllib.request.urlretrieve(url, MODEL_PATH)

# 2. Pygame 초기화 (라즈베리파이 7인치 세로 모드: 480x800)
pygame.init()
WIDTH, HEIGHT = 480, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("코행기 - 새 애니메이션 최적화")
clock = pygame.time.Clock()

# --- ✈️ 비행기 이미지 로드 ---
try:
    plane_img = pygame.image.load('images/plane_f.png').convert_alpha()
    plane_img = pygame.transform.scale(plane_img, (100, 50))
except FileNotFoundError:
    print("비행기 이미지 파일이 없습니다. 기본 색상으로 대체합니다.")
    plane_img = pygame.Surface((100, 50), pygame.SRCALPHA)
    plane_img.fill((0, 255, 122))

# --- 🦅 새 이미지 딕셔너리 로드 (1~4번 프레임 & 검은색 배경 제거) ---
bird_types = ["duck", "falcon", "goose", "pigeon", "seagull", "snipe"]
bird_animations = {}  # 일반 새 (1~4번 프레임)
flock_animations = {} # 편대 비행 (오리, 거위의 7~8번 프레임)

print("새 이미지 에셋을 불러오고 배경을 투명화합니다...")
for bird_type in bird_types:
    frames = []
    # 정면/위에서 본 모습인 1~4번 프레임만 불러옵니다.
    for i in range(1, 5):
        path = os.path.join("images", "birds", bird_type, f"{bird_type}_{i}.png")
        try:
            img = pygame.image.load(path).convert()
            img.set_colorkey((0, 0, 0)) # 검은색 배경 투명 처리
            img = pygame.transform.scale(img, (70, 70))
            frames.append(img)
        except FileNotFoundError:
            tmp_img = pygame.Surface((70, 70), pygame.SRCALPHA)
            pygame.draw.circle(tmp_img, (255, 100, 0), (35, 35), 35)
            frames.append(tmp_img)
    bird_animations[bird_type] = frames

    # 오리와 거위는 7~8번을 편대(보스) 이미지로 추가로 불러옵니다.
    if bird_type in ["duck", "goose"]:
        flock_frames = []
        for i in range(7, 9):
            path = os.path.join("images", "birds", bird_type, f"{bird_type}_{i}.png")
            try:
                img = pygame.image.load(path).convert()
                img.set_colorkey((0, 0, 0)) # 검은색 배경 투명 처리
                img = pygame.transform.scale(img, (160, 120)) # 편대는 더 크게
                flock_frames.append(img)
            except FileNotFoundError:
                pass
        if flock_frames:
            flock_animations[bird_type] = flock_frames
# ---------------------------------------------

# 3. MediaPipe 초기화
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.IMAGE,
    num_faces=1
)
detector = vision.FaceLandmarker.create_from_options(options)
cap = cv2.VideoCapture(0)

# 4. 게임 상태 및 글로벌 변수
game_state = "START"
RUNWAY_WIDTH = 120
scroll_offset = 0
scroll_speed = 8
health = 100.0
distance = 0.0

birds = []
bird_timer = 0
bird_speed_add = 2  
spawn_rate = 60     

btn_width, btn_height = 200, 60
normal_button = pygame.Rect(WIDTH//2 - btn_width//2, HEIGHT//2 - 20, btn_width, btn_height)
hard_button = pygame.Rect(WIDTH//2 - btn_width//2, HEIGHT//2 + 60, btn_width, btn_height)
retry_button = pygame.Rect(WIDTH//2 - btn_width//2, HEIGHT//2 + 60, btn_width, btn_height)

def set_difficulty(level):
    global scroll_speed, bird_speed_add, spawn_rate, RUNWAY_WIDTH
    if level == "NORMAL":
        scroll_speed = 8
        bird_speed_add = 2
        spawn_rate = 60
        RUNWAY_WIDTH = 120
    elif level == "HARD":
        scroll_speed = 12
        bird_speed_add = 5
        spawn_rate = 40
        RUNWAY_WIDTH = 100

def reset_game():
    global health, distance, scroll_offset, birds, bird_timer
    health = 100.0
    distance = 0.0
    scroll_offset = 0
    birds = []
    bird_timer = 0

def get_path_x(y, offset):
    return int(WIDTH // 2 + math.sin((y + offset) * 0.005) * 120)

font_title = pygame.font.SysFont(None, 60)
font_large = pygame.font.SysFont(None, 70)
font_medium = pygame.font.SysFont(None, 45)
font_small = pygame.font.SysFont(None, 36)

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            if game_state == "START":
                if normal_button.collidepoint(mouse_pos):
                    set_difficulty("NORMAL")
                    reset_game()
                    game_state = "PLAYING"
                elif hard_button.collidepoint(mouse_pos):
                    set_difficulty("HARD")
                    reset_game()
                    game_state = "PLAYING"
            elif game_state == "END":
                if retry_button.collidepoint(mouse_pos):
                    game_state = "START" 

    ret, frame = cap.read()
    if not ret:
        continue

    # --- 📷 웹캠 세로 모드 비율 크롭 ---
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    h, w, _ = rgb_frame.shape
    target_ratio = WIDTH / HEIGHT
    frame_ratio = w / h
    
    if frame_ratio > target_ratio:
        new_w = int(h * target_ratio)
        start_x = (w - new_w) // 2
        rgb_frame = rgb_frame[:, start_x:start_x+new_w]
        
    frame_resized = cv2.resize(rgb_frame, (WIDTH, HEIGHT))
    bg_surface = pygame.image.frombuffer(frame_resized.tobytes(), (WIDTH, HEIGHT), "RGB")

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_resized)
    detection_result = detector.detect(mp_image)
    
    nose_x, nose_y = WIDTH // 2, HEIGHT // 2 
    if detection_result.face_landmarks:
        nose_landmark = detection_result.face_landmarks[0][1]
        nose_x = int(nose_landmark.x * WIDTH)
        nose_y = int(nose_landmark.y * HEIGHT)

    plane_rect = plane_img.get_rect(center=(nose_x, nose_y))

    if game_state == "PLAYING":
        scroll_offset += scroll_speed
        distance += (scroll_speed * 0.05) 
        
        target_x = get_path_x(nose_y, scroll_offset)
        deviation = abs(nose_x - target_x)
        if deviation > RUNWAY_WIDTH // 2:
            health -= 0.5
            
        # 2. 난이도별 새 생성 로직
        bird_timer += 1
        if bird_timer > spawn_rate:
            bird_timer = 0
            if random.random() > 0.4: 
                spawn_y = -100
                spawn_x = get_path_x(spawn_y, scroll_offset) + random.randint(-40, 40)
                
                # 20% 확률로 거대 편대(Flock), 80% 확률로 일반 새(Single)
                if random.random() > 0.8 and flock_animations:
                    chosen_type = random.choice(list(flock_animations.keys()))
                    bird_style = "flock"
                else:
                    chosen_type = random.choice(list(bird_animations.keys()))
                    bird_style = "single"
                
                birds.append({
                    "x": spawn_x, 
                    "y": spawn_y, 
                    "type": chosen_type,
                    "style": bird_style,
                    "frame_idx": 0,    
                    "anim_timer": 0    
                })

        # 3. 새 이동 및 충돌 판정
        for bird in birds[:]:
            bird["y"] += scroll_speed + bird_speed_add
            
            # --- 애니메이션 업데이트 ---
            bird["anim_timer"] += 1
            if bird["anim_timer"] >= 5:  # 프레임 전환 속도
                bird["anim_timer"] = 0
                anim_list = flock_animations[bird["type"]] if bird["style"] == "flock" else bird_animations[bird["type"]]
                max_frames = len(anim_list)
                bird["frame_idx"] = (bird["frame_idx"] + 1) % max_frames
            
            # 현재 프레임 이미지 가져오기
            anim_list = flock_animations[bird["type"]] if bird["style"] == "flock" else bird_animations[bird["type"]]
            current_img = anim_list[bird["frame_idx"]]
            bird_rect = current_img.get_rect(center=(bird["x"], int(bird["y"])))
            
            if plane_rect.colliderect(bird_rect):
                damage = 30 if bird["style"] == "flock" else 15
                health -= damage
                birds.remove(bird)
            elif bird["y"] > HEIGHT + 100:
                birds.remove(bird)

        if health <= 0:
            health = 0
            game_state = "END"
                
    # --- 🎨 화면 그리기 ---
    screen.blit(bg_surface, (0, 0))

    # 활주로
    path_points = []
    for y in range(0, HEIGHT + 1, 20):
        x = get_path_x(y, scroll_offset)
        path_points.append((x, y))

    if len(path_points) > 1:
        pygame.draw.lines(screen, (200, 200, 200), False, path_points, RUNWAY_WIDTH)
        pygame.draw.lines(screen, (255, 200, 0), False, path_points, 4)

    # 비행기 이탈 경고 이펙트
    target_x = get_path_x(nose_y, scroll_offset)
    if game_state == "PLAYING" and abs(nose_x - target_x) > RUNWAY_WIDTH // 2:
        pygame.draw.circle(screen, (255, 50, 50), (nose_x, nose_y), 50, 5)
    screen.blit(plane_img, plane_rect)

    # 새 렌더링
    for bird in birds:
        anim_list = flock_animations[bird["type"]] if bird["style"] == "flock" else bird_animations[bird["type"]]
        current_img = anim_list[bird["frame_idx"]]
        bird_rect = current_img.get_rect(center=(bird["x"], int(bird["y"])))
        
        halo_radius = 45 if bird["style"] == "single" else 90
        pygame.draw.circle(screen, (255, 220, 0), (bird["x"], int(bird["y"])), halo_radius, 4)
        
        screen.blit(current_img, bird_rect)

    # UI 렌더링
    if game_state == "START":
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))
        
        title_text = font_title.render("NOSE AIRPLANE", True, (255, 255, 255))
        screen.blit(title_text, (WIDTH//2 - title_text.get_width()//2, HEIGHT//4))
        
        pygame.draw.rect(screen, (0, 200, 100), normal_button, border_radius=10)
        norm_text = font_medium.render("NORMAL", True, (255, 255, 255))
        screen.blit(norm_text, (normal_button.centerx - norm_text.get_width()//2, normal_button.centery - norm_text.get_height()//2))

        pygame.draw.rect(screen, (200, 50, 50), hard_button, border_radius=10)
        hard_text = font_medium.render("HARD", True, (255, 255, 255))
        screen.blit(hard_text, (hard_button.centerx - hard_text.get_width()//2, hard_button.centery - hard_text.get_height()//2))

    elif game_state == "PLAYING":
        pygame.draw.rect(screen, (50, 50, 50), (20, 20, 200, 20))
        pygame.draw.rect(screen, (255, 50, 50), (20, 20, 2 * health, 20))
        hp_text = font_small.render(f"HP: {int(health)}", True, (255, 255, 255))
        screen.blit(hp_text, (20, 45))
        
        dist_text = font_medium.render(f"Dist: {int(distance)}m", True, (0, 255, 255))
        dist_shadow = font_medium.render(f"Dist: {int(distance)}m", True, (0, 0, 0))
        screen.blit(dist_shadow, (WIDTH - dist_text.get_width() - 18, 22))
        screen.blit(dist_text, (WIDTH - dist_text.get_width() - 20, 20))

    elif game_state == "END":
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        over_text = font_large.render("GAME OVER", True, (255, 50, 50))
        screen.blit(over_text, (WIDTH//2 - over_text.get_width()//2, HEIGHT//4))
        
        result_text = font_medium.render(f"Score: {int(distance)}m", True, (255, 255, 0))
        screen.blit(result_text, (WIDTH//2 - result_text.get_width()//2, HEIGHT//4 + 80))
        
        pygame.draw.rect(screen, (255, 150, 0), retry_button, border_radius=10)
        retry_text = font_medium.render("MENU", True, (255, 255, 255))
        screen.blit(retry_text, (retry_button.centerx - retry_text.get_width()//2, retry_button.centery - retry_text.get_height()//2))

    pygame.display.flip()
    clock.tick(60)

cap.release()
pygame.quit()
sys.exit()