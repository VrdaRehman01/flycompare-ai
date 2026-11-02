export type ThemePreference = 'light' | 'dark' | 'system';
export type TripType = 'round-trip' | 'one-way' | 'multi-city';
export type DataStatus = 'demo' | 'test' | 'live';
export type Cabin = 'Economy' | 'Premium economy' | 'Business' | 'First class';
export const CABINS: Cabin[] = ['Economy', 'Premium economy', 'Business', 'First class'];

export type Amenity = { available: boolean | null; cost?: string | null };
export type CabinAmenities = { wifi?: Amenity | null; power?: Amenity | null; seat?: { type?: string | null; pitch?: string | null; legroom?: string | null } | null };
export type Segment = {
  id?: string | null; airline?: string | null; airline_code?: string | null; operating_airline?: string | null; marketing_airline?: string | null;
  flight_number?: string | null; origin: string; destination: string; origin_terminal?: string | null; destination_terminal?: string | null;
  departing_at: string; arriving_at: string; duration_minutes?: number | null; aircraft?: string | null; aircraft_code?: string | null;
  cabin?: string | null; cabin_marketing_name?: string | null; amenities?: CabinAmenities | null; technical_stops?: string[];
};
export type Itinerary = {
  origin: string; destination: string; departing_at: string; arriving_at: string; duration_minutes?: number | null; stops: number; segments: Segment[];
  fare_brand_name?: string | null; priority_check_in?: boolean | null; priority_boarding?: boolean | null; advance_seat_selection?: boolean | null;
};
export type Baggage = { baggage_type: string; quantity?: number | null; weight?: number | null; weight_unit?: string | null; passenger_type?: string | null; passenger_id?: string | null; slice_index?: number | null };
export type Flight = {
  id: string; provider: string; data_status: DataStatus; retrieved_at: string; airline: string; flight_number: string;
  origin: string; destination: string; departure_date: string; departure_time: string; arrival_time: string;
  duration_minutes: number; stops: number; price: number; currency: string; baggage_kg: number | null; cabin: string;
  refundable: boolean | null; disclaimer: string; itineraries?: Itinerary[]; baggage_allowances?: Baggage[];
  conditions?: FareConditions | null;
  airline_code?: string | null; airline_logo_url?: string | null; conditions_of_carriage_url?: string | null;
  base_amount?: number | null; base_currency?: string | null; tax_amount?: number | null; tax_currency?: string | null;
  expires_at?: string | null; total_emissions_kg?: number | null; passenger_count?: number | null;
  supports_seat_maps?: boolean; supports_extra_services?: boolean;
};
export type SeatService = { id: string; passenger_id: string; amount: number | null; currency: string | null };
export type SeatElement = { type: 'seat'; designator: string; name: string | null; disclosures: string[]; available: boolean; services: SeatService[] } | { type: string };
export type SeatMap = { segment_id: string | null; slice_id: string | null; cabins: { cabin_class: string | null; deck: number | null; aisles: number | null; wings: { first_row_index: number; last_row_index: number } | null; rows: SeatElement[][][] }[] };
export type SeatMapResponse = { supported: boolean; data_status: DataStatus; seat_maps: SeatMap[]; message: string | null };
export type BagService = {
  id: string; bag_type: string | null; maximum_weight_kg: number | null; maximum_length_cm: number | null; maximum_height_cm: number | null; maximum_depth_cm: number | null;
  amount: number | null; currency: string | null; maximum_quantity: number | null; passenger_ids: string[]; segment_ids: string[];
};
export type OfferDetails = {
  supported: boolean; data_status: DataStatus; message?: string; checked_at?: string; offer_id?: string; total_amount?: number | null; total_currency?: string | null;
  base_amount?: number | null; tax_amount?: number | null; tax_currency?: string | null; expires_at?: string | null; price_guarantee_expires_at?: string | null;
  passengers?: { id: string; type: string | null; age: number | null }[]; baggage_services?: BagService[]; conditions_of_carriage_url?: string | null;
};
export type FareCondition = { allowed: boolean | null; penalty_amount: number | null; penalty_currency: string | null };
export type FareConditions = { refund_before_departure: FareCondition | null; change_before_departure: FareCondition | null };

/** A verified airport selected from the airport dataset. */
export type AirportRef = { code: string; name: string; city: string; country: string; country_code?: string; lat?: number; lon?: number };
export type Leg = { origin: AirportRef | null; destination: AirportRef | null; date: string };
/** Children are described by age (2–17), as the provider requires. */
export type Passengers = { adults: number; childAges: number[]; infants: number };
export type SearchForm = {
  tripType: TripType; origin: AirportRef | null; destination: AirportRef | null; departure: string; returnDate: string;
  passengers: Passengers; cabin: Cabin; legs: Leg[];
};
export type SearchResponse = { data_status: DataStatus; source_message: string; results: Flight[]; search_id?: number | null; provider?: string | null };
export type SearchState = { query: SearchForm; response: SearchResponse; searchedAt: string };

export type HistoryItem = {
  id: number; origin: string; destination: string; origin_code: string | null; destination_code: string | null;
  departure_date: string; return_date: string | null; trip_type: TripType; passengers: number; children?: number; infants?: number; cabin: string;
  legs?: { origin: string; destination: string; departure_date: string }[] | null; result_count: number; data_status: DataStatus | null; currency: string | null; min_price: number | null; created_at: string;
};

export type Preferences = { home_airport?: string | null; cabin?: Cabin | null; passengers?: number | null; currency?: string | null; theme?: ThemePreference | null };
export type User = { id: number; name: string; email: string; preferences: Preferences; created_at: string; email_verified?: boolean; has_password?: boolean };
/** Returned instead of a user when an emailed code must be entered first. */
export type CodePending = { verification_required: true; email: string; expires_in_seconds: number; resend_after_seconds: number };
export type SavedFlight = { id: number; offer_id: string; offer: Flight; search: SearchForm | null; saved_at: string };

export type Airport = {
  code: string; icao: string | null; name: string; city: string; country: string; country_code: string; region: string;
  lat: number; lon: number; timezone: string | null; importance: number; distance_km?: number;
};
export type Destination = {
  key: string; city: string; country: string; country_code: string; region: string; lat: number; lon: number; airport: string;
  airports: { code: string; name: string }[]; themes: string[]; curated: boolean; distance_km: number | null;
  availability: { status: 'suggestion' } | { status: 'seen_in_searches'; direct_seen: boolean; last_seen: string; searches: number; airport: string };
};
export type DestinationPage = { origin: Airport | null; total: number; page: number; page_size: number; regions: string[]; themes: string[]; themes_note: string; route_note: string; items: Destination[] };
export type DestinationImage = {
  key: string; available: boolean; pending?: boolean; url?: string; url_2x?: string | null; licence?: string; artist?: string;
  file_url?: string; page_url?: string | null; source?: string; retrieved_at?: string;
};
export type RouteInfo = { origin: Airport; destination: Airport; distance_km: number; hubs: (Airport & { offers: number })[]; latest: RouteSnapshot; note: string };
export type RouteDailyHistory = { basis: string; requirements: { min_days: number }; groups: { currency: string; data_status: DataStatus; sufficient_for_trend: boolean; points: { date: string; lowest_price: number; offers: number; searches: number }[] }[] };

export type AnalyticsRange = '7d' | '30d' | '90d' | 'all';
export type Analytics = {
  range: AnalyticsRange; scope: 'me' | 'all'; generated_at: string;
  totals: { all_time_searches: number; period_searches: number; unique_destinations: number; unique_routes: number; average_offers_per_search: number | null; searches_with_no_offers: number };
  most_searched_route: RouteCount | null;
  activity: { granularity: 'day' | 'week' | 'month'; points: { start: string; count: number }[] };
  top_destinations: { code: string; label: string; count: number; share: number }[];
  top_routes: RouteCount[];
  cabins: { cabin: string; count: number; share: number }[];
  passengers: { passengers: number; count: number; share: number }[];
  trip_types: { trip_type: string; count: number }[];
  travel_heatmap: { month: number; weekday: number; count: number }[];
  departure_months: { month: string; count: number }[];
  passenger_types: { adults: number; children: number; infants: number };
  airlines: { basis: string; items: { airline: string; offers: number; searches: number; airline_code?: string | null; airline_logo_url?: string | null }[] };
  fares: { currency: string; data_status: DataStatus; offers: number; searches: number; average_offer_price: number; median_offer_price: number; average_lowest_price: number | null }[];
  data_status_mix: Record<string, number>;
  recent_searches?: HistoryItem[];
};
export type RouteCount = { origin: string; destination: string; origin_label: string; destination_label: string; count: number; share: number };

export type PricePoint = { observed_at: string; lowest_price: number; median_price: number; offers: number };
export type PriceHistory = {
  requirements: { min_points: number; min_distinct_days: number };
  groups: { currency: string; data_status: DataStatus; points: PricePoint[]; distinct_days: number; sufficient_for_trend: boolean; lowest_change: { absolute: number; percent: number | null } | null }[];
};
export type FareEstimate = {
  available: boolean; label: string; reason?: string; estimate?: number; currency?: string; month?: string; trip?: string;
  basis?: string; model_name?: string; holdout_mae?: number; holdout_month?: string; origin_city?: string; destination_city?: string;
};
export type RouteSnapshot = {
  origin: string; destination: string; available: boolean; lowest_price?: number; currency?: string; data_status?: DataStatus;
  airline?: string; observed_at?: string; departure_date?: string; return_date?: string | null; trip_type?: TripType; cabin?: string; passengers?: number;
};
export type Rates = { base: string; date: string; source: string; rates: Record<string, number> };

export type Place = { code: string; city: string; country: string | null; country_code: string | null; key: string | null };
export type DealCategory = { key: string; label: string; rule: string };
export type Deal = {
  id: string; origin: Place; destination: Place; themes: string[]; trip_type: TripType; cabin: string; passengers: number; currency: string;
  data_status: DataStatus; provider: string; kind: 'last_seen' | 'historical'; age_hours: number;
  price: number; airline: string; airline_code: string | null; airline_logo_url: string | null; stops: number;
  departure_date: string; return_date: string | null; observed_at: string;
  change: { previous_price: number; previous_observed_at: string; absolute: number; percent: number | null } | null;
  flexibility: { dates_observed: number; first_date: string; last_date: string; cheapest: { departure_date: string; return_date: string | null; price: number; observed_at: string } };
  categories: string[];
};
export type DealsResponse = { generated_at: string; origin: string | null; basis: string; rules: { fresh_days: number; recent_hours: number }; categories: DealCategory[]; items: Deal[] };
export type PopularRoute = {
  origin: Place; destination: Place; searches: number; share: number; data_status_mix: Record<string, number>; last_fare: RouteSnapshot | null;
  last_searched_at?: string; last_searched_day?: string; saved?: boolean;
  last_trip?: { trip_type: TripType; departure_date: string; return_date: string | null; cabin: string; passengers: number };
};
export type PopularRoutes = { scope: 'me' | 'all'; total_searches: number; routes: PopularRoute[]; basis: string; min_public_searches: number };
export type SavedRoute = { origin: Place; destination: Place; saved_at: string; last_fare: RouteSnapshot | null };
