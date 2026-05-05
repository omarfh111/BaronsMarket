def assign_box_to_queue(box, zones, min_overlap=0.10):
    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

    # FOOT position (critical)
    foot_x = int((x1 + x2) / 2)
    foot_y = int(y2)

    best_zone = None
    best_overlap = 0.0

    for name, zone in zones.items():

        # 🔹 1. Check FOOT is inside zone (hard constraint)
        inside = cv2.pointPolygonTest(zone, (foot_x, foot_y), False) >= 0
        if not inside:
            continue

        # 🔹 2. Then check overlap (soft constraint)
        overlap = bbox_zone_overlap((x1, y1, x2, y2), zone)

        if overlap > best_overlap:
            best_overlap = overlap
            best_zone = name

    if best_zone is not None and best_overlap >= min_overlap:
        return best_zone, best_overlap

    return None, best_overlap


def choose_best_queue(queue_counts, min_valid_count=1):
    valid = {q: c for q, c in queue_counts.items() if c >= min_valid_count}

    if len(valid) == 0:
        return min(queue_counts, key=queue_counts.get)

    return min(valid, key=valid.get)
