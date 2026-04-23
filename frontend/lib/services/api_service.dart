import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../models/product.dart';

class ApiService {
  static const String _defaultBaseUrl = 'http://10.0.2.2:8000';
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
}
