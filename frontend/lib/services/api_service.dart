import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../models/assistant_chat.dart';
import '../models/catalog_product.dart';
import '../models/checkout_save.dart';
import '../models/fidelity_card_result.dart';
import '../models/meat_freshness_result.dart';
import '../models/product.dart';
import '../models/queue_recommendation.dart';

class ApiService {
  static const String _defaultBaseUrl = '10.0.0.1:8000';
  final String baseUrl;

  ApiService({
    String? baseUrl,
  }) : baseUrl = baseUrl ??
            const String.fromEnvironment(
              'API_BASE_URL',
              defaultValue: _defaultBaseUrl,
            );

  Future<List<Product>> detectProducts(File imageFile, {int topK = 3}) async {
    final uri = Uri.parse('$baseUrl/detect?top_k=$topK');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(
        await http.MultipartFile.fromPath(
          'image',
          imageFile.path,
          contentType: MediaType('image', 'jpeg'),
        ),
      );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode >= 400) {
      throw Exception('Detect failed: ${response.statusCode} ${response.body}');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final list = (body['predictions'] as List<dynamic>? ?? [])
        .map((entry) => Product.fromJson(entry as Map<String, dynamic>))
        .toList();
    return list;
  }

  Future<MeatFreshnessResult> detectMeatFreshness(File imageFile) async {
    final uri = Uri.parse('$baseUrl/meat-freshness');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(
        await http.MultipartFile.fromPath(
          'image',
          imageFile.path,
          contentType: MediaType('image', 'jpeg'),
        ),
      );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode >= 400) {
      throw Exception('Meat freshness failed: ${response.statusCode} ${response.body}');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return MeatFreshnessResult.fromJson(body);
  }

  Future<MeatFreshnessResult> detectVegetableFreshness(File imageFile) async {
    final uri = Uri.parse('$baseUrl/vegetable-freshness');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(
        await http.MultipartFile.fromPath(
          'image',
          imageFile.path,
          contentType: MediaType('image', 'jpeg'),
        ),
      );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode >= 400) {
      throw Exception('Vegetable freshness failed: ${response.statusCode} ${response.body}');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return MeatFreshnessResult.fromJson(body);
  }

  Future<QueueRecommendation> getLatestQueueRecommendation() async {
    final uri = Uri.parse('$baseUrl/queue-recommendation/latest');
    final response = await http.get(uri);
    if (response.statusCode >= 400) {
      throw Exception('Queue latest failed: ${response.statusCode} ${response.body}');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return QueueRecommendation.fromJson(body);
  }

  Future<CatalogResponse> getCatalogProducts({
    int page = 1,
    int pageSize = 30,
    String? category,
    String? query,
  }) async {
    final params = <String, String>{
      'page': '$page',
      'page_size': '$pageSize',
    };
    if (category != null && category.trim().isNotEmpty) {
      params['category'] = category.trim();
    }
    if (query != null && query.trim().isNotEmpty) {
      params['query'] = query.trim();
    }

    final uri = Uri.parse('$baseUrl/catalog/products').replace(queryParameters: params);
    final response = await http.get(uri);

    if (response.statusCode >= 400) {
      throw Exception('Catalog failed: ${response.statusCode} ${response.body}');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final data = CatalogResponse.fromJson(body);
    final normalizedItems = data.items
        .map(
          (item) => CatalogProduct(
            id: item.id,
            name: item.name,
            brand: item.brand,
            price: item.price,
            category: item.category,
            image: item.image.startsWith('http')
                ? item.image
                : '$baseUrl${item.image.startsWith('/') ? '' : '/'}${item.image}',
          ),
        )
        .toList();
    return CatalogResponse(
      items: normalizedItems,
      total: data.total,
      page: data.page,
      pageSize: data.pageSize,
      categories: data.categories,
    );
  }

  Future<AssistantChatResponse> sendAssistantMessage({
    required String message,
    String? sessionId,
    double? budgetTnd,
    List<AssistantCartItemPayload> cartItems = const [],
  }) async {
    final uri = Uri.parse('$baseUrl/assistant/chat');
    final payload = <String, dynamic>{
      'message': message,
      'session_id': sessionId,
      'budget_tnd': budgetTnd,
      'cart_items': cartItems.map((e) => e.toJson()).toList(),
    };
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    if (response.statusCode >= 400) {
      throw Exception('Assistant failed: ${response.statusCode} ${response.body}');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final parsed = AssistantChatResponse.fromJson(body);
    final normalizedProducts = parsed.recommendedProducts
        .map(
          (p) => AssistantRecommendedProduct(
            id: p.id,
            name: p.name,
            brand: p.brand,
            price: p.price,
            image: p.image.startsWith('http')
                ? p.image
                : '$baseUrl${p.image.startsWith('/') ? '' : '/'}${p.image}',
            quantity: p.quantity,
            reason: p.reason,
          ),
        )
        .toList();
    return AssistantChatResponse(
      sessionId: parsed.sessionId,
      activeAgent: parsed.activeAgent,
      assistantMessage: parsed.assistantMessage,
      mode: parsed.mode,
      steps: parsed.steps,
      showProductsNow: parsed.showProductsNow,
      recommendedProducts: normalizedProducts,
    );
  }

  Future<CheckoutSaveResponse> saveCheckout({
    required String? cartId,
    required int? createdAtUnixMs,
    required String recommendedQueue,
    required double totalPrice,
    required List<AssistantCartItemPayload> items,
    Map<String, dynamic> metadata = const {},
  }) async {
    final uri = Uri.parse('$baseUrl/checkout/save');
    final payload = <String, dynamic>{
      'cart_id': cartId,
      'created_at_unix_ms': createdAtUnixMs,
      'recommended_queue': recommendedQueue,
      'total_price': totalPrice,
      'items': items.map((e) => e.toJson()).toList(),
      'metadata': metadata,
    };
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    if (response.statusCode >= 400) {
      throw Exception('Checkout save failed: ${response.statusCode} ${response.body}');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return CheckoutSaveResponse.fromJson(body);
  }

  Future<FidelityCardResult> verifyFidelityCard(File imageFile) async {
    final uri = Uri.parse('$baseUrl/fidelity/verify');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(
        await http.MultipartFile.fromPath(
          'image',
          imageFile.path,
          contentType: MediaType('image', 'jpeg'),
        ),
      );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);
    if (response.statusCode >= 400) {
      throw Exception('Fidelity verify failed: ${response.statusCode} ${response.body}');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return FidelityCardResult.fromJson(body);
  }
}
