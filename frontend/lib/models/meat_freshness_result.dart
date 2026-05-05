class MeatFreshnessResult {
  final String label;
  final double confidence;
  final Map<String, double> probabilities;

  const MeatFreshnessResult({
    required this.label,
    required this.confidence,
    required this.probabilities,
  });

  factory MeatFreshnessResult.fromJson(Map<String, dynamic> json) {
    final rawProbs = (json['probabilities'] as Map<String, dynamic>? ?? {});
    final probs = <String, double>{};
    rawProbs.forEach((key, value) {
      probs[key] = (value as num?)?.toDouble() ?? 0.0;
    });

    return MeatFreshnessResult(
      label: (json['label'] ?? 'Unknown').toString(),
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      probabilities: probs,
    );
  }
}

