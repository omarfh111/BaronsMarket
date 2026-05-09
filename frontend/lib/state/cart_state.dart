import 'package:flutter/foundation.dart';

import '../models/product.dart';

class CartState extends ChangeNotifier {
  final Map<String, CartItem> _items = {};
  static const int fastCourseMaxItems = 15;
  String? _cartId;
  int? _createdAtUnixMs;
  bool _loyaltyApplied = false;
  int _loyaltyDiscountPercent = 0;
  String? _loyaltyCardId;
  String? _loyaltyCustomerName;

  List<CartItem> get items => _items.values.toList();

  int get totalItems =>
      _items.values.fold<int>(0, (sum, item) => sum + item.quantity);
  int get catalogItemsCount => _items.values
      .where((item) => item.product.isCatalogSource)
      .fold<int>(0, (sum, item) => sum + item.quantity);
  bool get hasCatalogItems => _items.values.any((item) => item.product.isCatalogSource);
  bool get hasRegularItems => _items.values.any((item) => !item.product.isCatalogSource);
  bool get useFastCourse => hasCatalogItems && !hasRegularItems;

  double get totalPrice => _items.values.fold<double>(
    0,
    (sum, item) => sum + item.subtotal,
  );
  String? get cartId => _cartId;
  int? get createdAtUnixMs => _createdAtUnixMs;
  bool get loyaltyApplied => _loyaltyApplied;
  int get loyaltyDiscountPercent => _loyaltyDiscountPercent;
  String? get loyaltyCardId => _loyaltyCardId;
  String? get loyaltyCustomerName => _loyaltyCustomerName;
  double get discountedTotalPrice {
    if (!_loyaltyApplied || _loyaltyDiscountPercent <= 0) return totalPrice;
    final ratio = (100 - _loyaltyDiscountPercent) / 100.0;
    return totalPrice * ratio;
  }

  void applyLoyalty({
    required int discountPercent,
    required String? cardId,
    required String? customerName,
  }) {
    _loyaltyApplied = discountPercent > 0;
    _loyaltyDiscountPercent = discountPercent > 0 ? discountPercent : 0;
    _loyaltyCardId = cardId;
    _loyaltyCustomerName = customerName;
    notifyListeners();
  }

  void clearLoyalty() {
    _loyaltyApplied = false;
    _loyaltyDiscountPercent = 0;
    _loyaltyCardId = null;
    _loyaltyCustomerName = null;
    notifyListeners();
  }

  String? addProduct(Product product) {
    if (product.isCatalogSource && catalogItemsCount >= fastCourseMaxItems) {
      return 'Fast Course limit reached (15 products max).';
    }

    final key = '${product.name}_${product.brand}';
    if (_items.containsKey(key)) {
      _items[key]!.quantity += 1;
    } else {
      _items[key] = CartItem(product: product);
    }
    _createdAtUnixMs ??= DateTime.now().millisecondsSinceEpoch;
    _cartId ??= 'cart_${_createdAtUnixMs!}';
    notifyListeners();
    return null;
  }

  void removeOne(CartItem item) {
    final key = '${item.product.name}_${item.product.brand}';
    if (!_items.containsKey(key)) return;
    final existing = _items[key]!;
    if (existing.quantity <= 1) {
      _items.remove(key);
    } else {
      existing.quantity -= 1;
    }
    notifyListeners();
  }

  void clear() {
    _items.clear();
    _cartId = null;
    _createdAtUnixMs = null;
    _loyaltyApplied = false;
    _loyaltyDiscountPercent = 0;
    _loyaltyCardId = null;
    _loyaltyCustomerName = null;
    notifyListeners();
  }
}
