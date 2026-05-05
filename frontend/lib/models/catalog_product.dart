import 'product.dart';

class CatalogProduct {
  final String id;
  final String name;
  final String brand;
  final double price;
  final String category;
  final String image;

  const CatalogProduct({
    required this.id,
    required this.name,
    required this.brand,
    required this.price,
    required this.category,
    required this.image,
  });

  factory CatalogProduct.fromJson(Map<String, dynamic> json) {
    return CatalogProduct(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? 'Unknown Product').toString(),
      brand: (json['brand'] ?? 'Unknown Brand').toString(),
      price: (json['price'] as num?)?.toDouble() ?? 0.0,
      category: (json['category'] ?? 'Other').toString(),
      image: (json['image'] ?? '').toString(),
    );
  }

  Product toCartProduct() {
    return Product(
      name: name,
      brand: brand,
      price: price,
      image: image,
      isCatalogSource: true,
      confidence: null,
      detectorConfidence: null,
    );
  }
}

class CatalogResponse {
  final List<CatalogProduct> items;
  final int total;
  final int page;
  final int pageSize;
  final List<String> categories;

  const CatalogResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.categories,
  });

  factory CatalogResponse.fromJson(Map<String, dynamic> json) {
    final entries = (json['items'] as List<dynamic>? ?? [])
        .map((e) => CatalogProduct.fromJson(e as Map<String, dynamic>))
        .toList();
    return CatalogResponse(
      items: entries,
      total: (json['total'] as num?)?.toInt() ?? 0,
      page: (json['page'] as num?)?.toInt() ?? 1,
      pageSize: (json['page_size'] as num?)?.toInt() ?? 30,
      categories: (json['categories'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
    );
  }
}
