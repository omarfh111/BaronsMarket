class FidelityCardResult {
  final bool valid;
  final int discountPercent;
  final String message;
  final String? cardId;
  final String? customerName;

  const FidelityCardResult({
    required this.valid,
    required this.discountPercent,
    required this.message,
    this.cardId,
    this.customerName,
  });

  factory FidelityCardResult.fromJson(Map<String, dynamic> json) {
    return FidelityCardResult(
      valid: (json['valid'] as bool?) ?? false,
      discountPercent: (json['discount_percent'] as num?)?.toInt() ?? 0,
      message: (json['message'] ?? '').toString(),
      cardId: json['card_id']?.toString(),
      customerName: json['customer_name']?.toString(),
    );
  }
}
