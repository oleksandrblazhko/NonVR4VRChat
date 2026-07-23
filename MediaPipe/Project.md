# Документація алгоритмів MediaPipe4VRChat

Цей документ містить покроковий аналіз та математичний опис ключових алгоритмів проекту [MediaPipe4VRChat](file:///C:/Users/User/Yoga/Yoga/MediaPipe4VRChat):
1.  **Відстеження:** Обчислення 3D-орієнтації тулуба ([BodyTracker](file:///C:/Users/User/Yoga/Yoga/MediaPipe4VRChat/body_tracker.py#L71)).
2.  **Логіка керування:** Обробка, фільтрація та відображення кутів у OSC-команди ([LookController](file:///C:/Users/User/Yoga/Yoga/MediaPipe4VRChat/look_controller.py#L87)).

---

## ЧАСТИНА 1. Відстеження 3D-орієнтації тулуба (BodyTracker)

### 1.1. Вхідні дані
Алгоритм використовує координати суглобів із тривимірного простору MediaPipe, представлені об'єктом [Skeleton](file:///C:/Users/User/Yoga/Yoga/MediaPipe4VRChat/pose_types.py#L35):
*   Плечі: $P_{left\_shoulder}$ та $P_{right\_shoulder}$
*   Стегна: $P_{left\_hip}$ та $P_{right\_hip}$

Кожна точка є об'єктом типу [Vector3](file:///C:/Users/User/Yoga/Yoga/MediaPipe4VRChat/math3d.py#L25) з координатами $(x, y, z)$.

### 1.2. Покроковий опис алгоритму відстеження

```mermaid
graph TD
    subgraph Вхідні дані
        S[Ліве/Праве плече]
        H[Ліве/Праве стегно]
    end

    subgraph Крок 1: Розрахунок центрів
        S -->|Середнє значення| SC[Центр плечей C_shoulder]
        H -->|Середнє значення| HC[Центр стегон C_hip]
    end

    subgraph Крок 2: Векторний аналіз
        SC & HC -->|Різниця векторів| VT[Вектор тулуба V_torso]
        S -->|Різниця векторів| VS[Вектор плечей V_shoulder]
        VT -->|Нормалізація| VT_N[Нормалізований вектор тулуба]
        VS -->|Нормалізація| VS_N[Нормалізований вектор плечей]
    end

    subgraph Крок 3: Кути орієнтації
        VS_N -->|yaw = -atan2(x, z)| Yaw[Абсолютний Yaw]
        VT_N -->|pitch = atan2(y, z)| Pitch[Абсолютний Pitch]
    end
```

#### Крок 1: Обчислення центрів плечей та стегон
Для мінімізації локальних коливань обчислюються середні точки:
1.  **Центр плечей** ($\mathbf{C}_{shoulder}$):
    $$\mathbf{C}_{shoulder} = \frac{\mathbf{P}_{left\_shoulder} + \mathbf{P}_{right\_shoulder}}{2}$$
2.  **Центр стегон** ($\mathbf{C}_{hip}$):
    $$\mathbf{C}_{hip} = \frac{\mathbf{P}_{left\_hip} + \mathbf{P}_{right\_hip}}{2}$$

#### Крок 2: Формування та нормалізація напрямних векторів
1.  **Вектор плечей** ($\mathbf{V}_{shoulder}$):
    Напрямок від лівого плеча до правого:
    $$\mathbf{V}_{shoulder} = \mathbf{P}_{right\_shoulder} - \mathbf{P}_{left\_shoulder}$$
    Вектор нормалізується до одиничної довжини:
    $$\mathbf{\hat{V}}_{shoulder} = \text{normalize}(\mathbf{V}_{shoulder})$$
2.  **Вектор тулуба** ($\mathbf{V}_{torso}$):
    Напрямок від центру стегон до центру плечей (вертикальна вісь хребта):
    $$\mathbf{V}_{torso} = \mathbf{C}_{shoulder} - \mathbf{C}_{hip}$$
    Вектор нормалізується:
    $$\mathbf{\hat{V}}_{torso} = \text{normalize}(\mathbf{V}_{torso})$$

#### Крок 3: Обчислення кутів орієнтації (Yaw та Pitch)
*   **Кут повороту (Yaw / Обертання)**:
    Визначає поворот вліво/вправо навколо вертикальної осі. Обчислюється на основі проекцій вектора плечей на горизонтальну площину $(x, z)$:
    $$\text{yaw\_angle} = -\text{atan2}(\mathbf{\hat{V}}_{shoulder}.x, \mathbf{\hat{V}}_{shoulder}.z)$$
    *Примітка:* Знак мінус компенсує дзеркальність камери для системи координат VRChat.
*   **Кут нахилу (Pitch / Тангаж)**:
    Визначає нахил вперед/назад. Обчислюється через проекції вектора тулуба на площину $(y, z)$:
    $$\text{pitch\_angle} = \text{atan2}(\mathbf{\hat{V}}_{torso}.y, \mathbf{\hat{V}}_{torso}.z)$$

---

## ЧАСТИНА 2. Логіка керування (LookController)

Модуль [LookController](file:///C:/Users/User/Yoga/Yoga/MediaPipe4VRChat/look_controller.py#L87) обробляє отримані кути yaw та pitch, 
фільтрує шум і перетворює їх на нормовані значення погляду для VRChat.

### 2.1. Вхідні дані
*   Поточні абсолютні кути тіла: `yaw_angle` та `pitch_angle` (радіани).
*   Відкалібровані нейтральні кути: `neutral_yaw` та `neutral_pitch` (радіани).

### 2.2. Покроковий опис алгоритму керування

```mermaid
graph TD
    In[Абсолютні кути & Нейтральні кути] --> CalcRel[Крок 1: Обчислення відносних кутів у градусах]
    CalcRel --> Norm[Крок 2: Нормалізація з мертвою зоною та кривою]
    Norm --> MapVR[Крок 3: Відображення на координати VRChat]
    MapVR --> SmoothEMA[Крок 4: Експоненційне згладжування EMA]
    SmoothEMA --> Out[Фінальні LookHorizontal & LookVertical]
```

#### Крок 1: Обчислення відносних кутів у градусах
Для розрахунків відхилення від нейтрального стану обчислюється різниця кутів та переводиться у градуси:
$$\Delta\theta_{yaw} = \text{degrees}(\text{yaw\_angle} - \text{neutral\_yaw})$$
$$\Delta\theta_{pitch} = \text{degrees}(\text{pitch\_angle} - \text{neutral\_pitch})$$

#### Крок 2: Нормалізація та нелінійна обробка ([normalize_angle](file:///C:/Users/User/Yoga/Yoga/MediaPipe4VRChat/look_controller.py#L131))
Для кожного кута $\theta$ виконуються такі операції:
1.  **Застосування мертвої зони (Dead Zone)**:
    Якщо кут лежить у межах мертвої зони ($|\theta| \le \text{dead\_zone}$), рух ігнорується, і функція повертає $0.0$.
    Якщо кут виходить за межі, мертва зона віднімається для плавного старту:
    $$\theta_{clean} = \theta - \text{dead\_zone} \quad (\text{при } \theta > 0)$$
    $$\theta_{clean} = \theta + \text{dead\_zone} \quad (\text{при } \theta < 0)$$
2.  **Нормалізація**:
    Масштабування кута до діапазону $[-1.0, 1.0]$ на основі максимального робочого діапазону:
    $$\text{normalized} = \frac{\theta_{clean}}{\text{max\_limit} - \text{dead\_zone}}$$
3.  **Обмеження (Clamping)**:
    Значення примусово обмежується в межах $[-1.0, 1.0]$.
4.  **Квадратична характеристика**:
    Для підвищення точності біля центру та чутливості на великих кутах застосовується квадратична крива зі збереженням знаку:
    $$f(x) = \text{sign}(x) \cdot x^2$$

#### Крок 3: Відображення на простір координат VRChat
VRChat приймає значення погляду в діапазоні $[-1.0, 1.0]$, але нейтральне положення зміщене:
*   **Горизонтальний погляд (LookHorizontal)**:
    Центр знаходиться на рівні $0.5$ (при $Y_{norm} = 0$):
    $$H_{target} = 0.5 + 0.5 \cdot Y_{norm} \quad (\text{при } Y_{norm} > 0)$$
    $$H_{target} = -0.5 + 0.5 \cdot Y_{norm} \quad (\text{при } Y_{norm} < 0)$$
*   **Вертикальний погляд (LookVertical)**:
    Центр знаходиться на рівні $0.1$ (при $P_{norm} = 0$):
    $$V_{target} = 0.1 + 0.9 \cdot P_{norm} \quad (\text{при } P_{norm} > 0)$$
    $$V_{target} = -0.1 + 0.9 \cdot P_{norm} \quad (\text{при } P_{norm} < 0)$$

Отримані значення обмежуються функцією `clamp` у межах $[-1.0, 1.0]$.

#### Крок 4: Експоненційне згладжування (EMA)
Для фільтрації тремтіння камери та шумів детекції застосовується експоненційне ковзне середнє з коефіцієнтом згладжування $\alpha = 0.25$:
$$H_{smoothed} = H_{smoothed} + (H_{target} - H_{smoothed}) \cdot 0.25$$
$$V_{smoothed} = V_{smoothed} + (V_{target} - V_{smoothed}) \cdot 0.25$$

