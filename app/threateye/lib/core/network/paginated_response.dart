/// Generic wrapper for paginated API responses that use cursor-based pagination.
///
/// The SecureNet mobile gateway returns paginated lists in this shape:
/// ```json
/// {
///   "success": true,
///   "data": [ ...items... ],
///   "meta": {
///     "cursor":   "eyJpZCI6Mn0=",
///     "has_next": true,
///     "per_page": 20
///   }
/// }
/// ```
/// [T] is the domain entity or data model for a single item.
class PaginatedResponse<T> {
  /// The decoded list of items for this page.
  final List<T> items;

  /// Opaque cursor string to pass as `?cursor=` on the next request.
  /// `null` when [hasNext] is `false`.
  final String? cursor;

  /// `true` when there are more pages available after this one.
  final bool hasNext;

  const PaginatedResponse({
    required this.items,
    required this.cursor,
    required this.hasNext,
  });

  /// Deserialises from the raw API response body.
  ///
  /// [fromJsonItem] converts each element in `data` to type [T].
  factory PaginatedResponse.fromJson(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) fromJsonItem,
  ) {
    final rawData = json['data'];
    final List<dynamic> dataList =
        rawData is List ? rawData : [];

    final meta = json['meta'] as Map<String, dynamic>? ?? {};

    return PaginatedResponse<T>(
      items:   dataList.map((e) => fromJsonItem(e as Map<String, dynamic>)).toList(),
      cursor:  meta['cursor'] as String?,
      hasNext: meta['has_next'] as bool? ?? false,
    );
  }

  /// Convenience: an empty first page with no next page.
  static PaginatedResponse<T> empty<T>() => const PaginatedResponse(
        items:   [],
        cursor:  null,
        hasNext: false,
      );
}
