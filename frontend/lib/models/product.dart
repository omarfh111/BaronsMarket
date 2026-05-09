class Product {
  final String name;
  final String brand;
  final double price;
  final String image;
  final bool isCatalogSource;
  final double? confidence;
  final double? detectorConfidence;

  const Product({
    required this.name,
    required this.brand,
    required this.price,
    required this.image,
    this.isCatalogSource = false,
    this.confidence,
    this.detectorConfidence,
  });

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      name: (json['name'] ?? 'Unknown Product').toString(),
      brand: (json['brand'] ?? 'Unknown Brand').toString(),
      price: (json['price'] as num?)?.toDouble() ?? 0,
      image: (json['image'] ?? '').toString(),
      isCatalogSource: (json['is_catalog_source'] as bool?) ?? false,
      confidence: (json['confidence'] as num?)?.toDouble(),
      detectorConfidence: (json['detector_confidence'] as num?)?.toDouble(),
    );
  }
}

class CartItem {
  final Product product;
  int quantity;

  CartItem({required this.product, this.quantity = 1});

  double get subtotal => product.price * quantity;
}
