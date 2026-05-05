class AssistantCartItemPayload {
  final String? productId;
  final String name;
  final String brand;
  final int quantity;
  final double unitPrice;

  const AssistantCartItemPayload({
    this.productId,
    required this.name,
    required this.brand,
    required this.quantity,
    required this.unitPrice,
  });

  Map<String, dynamic> toJson() => {
        'product_id': productId,
        'name': name,
        'brand': brand,
        'quantity': quantity,
        'unit_price': unitPrice,
      };
}

class AssistantRecommendedProduct {
  final String id;
  final String name;
  final String brand;
  final double price;
  final String image;
  final int quantity;
  final String reason;

  const AssistantRecommendedProduct({
    required this.id,
    required this.name,
    required this.brand,
    required this.price,
    required this.image,
    required this.quantity,
    required this.reason,
  });

  factory AssistantRecommendedProduct.fromJson(Map<String, dynamic> json) {
    return AssistantRecommendedProduct(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      brand: (json['brand'] ?? '').toString(),
      price: (json['price'] as num?)?.toDouble() ?? 0,
      image: (json['image'] ?? '').toString(),
      quantity: (json['quantity'] as num?)?.toInt() ?? 1,
      reason: (json['reason'] ?? '').toString(),
    );
  }
}

class AssistantChatResponse {
  final String sessionId;
  final String activeAgent;
  final String assistantMessage;
  final String mode;
  final List<String> steps;
  final bool showProductsNow;
  final List<AssistantRecommendedProduct> recommendedProducts;

  const AssistantChatResponse({
    required this.sessionId,
    required this.activeAgent,
    required this.assistantMessage,
    required this.mode,
    required this.steps,
    required this.showProductsNow,
    required this.recommendedProducts,
  });

  factory AssistantChatResponse.fromJson(Map<String, dynamic> json) {
    return AssistantChatResponse(
      sessionId: (json['session_id'] ?? '').toString(),
      activeAgent: (json['active_agent'] ?? 'general').toString(),
      assistantMessage: (json['assistant_message'] ?? '').toString(),
      mode: (json['mode'] ?? 'step_by_step').toString(),
      steps: (json['steps'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
      showProductsNow: (json['show_products_now'] as bool?) ?? false,
      recommendedProducts: (json['recommended_products'] as List<dynamic>? ?? [])
          .map((e) => AssistantRecommendedProduct.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

