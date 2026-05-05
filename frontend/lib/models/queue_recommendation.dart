class QueueRecommendation {
  final String bestQueue;
  final Map<String, int> queueCounts;
  final int processedFrames;
  final double fps;

  const QueueRecommendation({
    required this.bestQueue,
    required this.queueCounts,
    required this.processedFrames,
    required this.fps,
  });

  factory QueueRecommendation.fromJson(Map<String, dynamic> json) {
    final rawCounts = (json['queue_counts'] as Map<String, dynamic>? ?? {});
    return QueueRecommendation(
      bestQueue: (json['best_queue'] ?? 'N/A').toString(),
      queueCounts: rawCounts.map((k, v) => MapEntry(k, (v as num?)?.toInt() ?? 0)),
      processedFrames: (json['processed_frames'] as num?)?.toInt() ?? 0,
      fps: (json['fps'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

