class CheckoutSaveResponse {
  final String cartId;
  final String recommendedQueue;
  final double totalPrice;
  final int checkoutAtUnixMs;
  final int? durationSeconds;
  final String storedIn;

  const CheckoutSaveResponse({
    required this.cartId,
    required this.recommendedQueue,
    required this.totalPrice,
    required this.checkoutAtUnixMs,
    required this.durationSeconds,
    required this.storedIn,
  });

  factory CheckoutSaveResponse.fromJson(Map<String, dynamic> json) {
    return CheckoutSaveResponse(
      cartId: (json['cart_id'] ?? '').toString(),
      recommendedQueue: (json['recommended_queue'] ?? '').toString(),
      totalPrice: (json['total_price'] as num?)?.toDouble() ?? 0,
      checkoutAtUnixMs: (json['checkout_at_unix_ms'] as num?)?.toInt() ?? 0,
      durationSeconds: (json['duration_seconds'] as num?)?.toInt(),
      storedIn: (json['stored_in'] ?? 'unknown').toString(),
    );
  }
}
