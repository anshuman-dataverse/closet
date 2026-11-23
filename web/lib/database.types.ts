export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type Database = {
  graphql_public: {
    Tables: {
      [_ in never]: never;
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      graphql: { Args: { extensions?: Json; operationName?: string; query?: string; variables?: Json }; Returns: Json };
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
  public: {
    Tables: {
      hunt_results: {
        Row: {
          checked_at: string;
          hunt_id: string;
          id: string;
          image_url: string | null;
          owned_item_id: string | null;
          price_cents: number | null;
          quality: string | null;
          rank: number;
          rating: number | null;
          rating_count: number | null;
          set_no: number | null;
          size_available: string;
          slot: string | null;
          store: string | null;
          title: string;
          url: string | null;
          user_id: string;
          was_price_cents: number | null;
          why: string | null;
        };
        ComputedFields: never;
        Insert: {
          checked_at?: string;
          hunt_id: string;
          id?: string;
          image_url?: string | null;
          owned_item_id?: string | null;
          price_cents?: number | null;
          quality?: string | null;
          rank: number;
          rating?: number | null;
          rating_count?: number | null;
          set_no?: number | null;
          size_available?: string;
          slot?: string | null;
          store?: string | null;
          title: string;
          url?: string | null;
          user_id?: string;
          was_price_cents?: number | null;
          why?: string | null;
        };
        Update: {
          checked_at?: string;
          hunt_id?: string;
          id?: string;
          image_url?: string | null;
          owned_item_id?: string | null;
          price_cents?: number | null;
          quality?: string | null;
          rank?: number;
          rating?: number | null;
          rating_count?: number | null;
          set_no?: number | null;
          size_available?: string;
          slot?: string | null;
          store?: string | null;
          title?: string;
          url?: string | null;
          user_id?: string;
          was_price_cents?: number | null;
          why?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "hunt_results_hunt_id_fkey";
            columns: ["hunt_id"];
            isOneToOne: false;
            referencedRelation: "hunts";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "hunt_results_owned_item_id_fkey";
            columns: ["owned_item_id"];
            isOneToOne: false;
            referencedRelation: "item_stats";
            referencedColumns: ["item_id"];
          },
          {
            foreignKeyName: "hunt_results_owned_item_id_fkey";
            columns: ["owned_item_id"];
            isOneToOne: false;
            referencedRelation: "items";
            referencedColumns: ["id"];
          },
        ];
      };
      hunts: {
        Row: {
          budget_max_cents: number | null;
          budget_min_cents: number | null;
          created_at: string;
          error: string | null;
          finished_at: string | null;
          id: string;
          kind: string;
          look_mode: string | null;
          look_types: Json | null;
          notes: string | null;
          occasion: Database["public"]["Enums"]["occasion"] | null;
          pages_checked: number;
          provider: string;
          query: string;
          started_at: string | null;
          status: Database["public"]["Enums"]["job_status"];
          summary: string | null;
          use_gpt: boolean;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          budget_max_cents?: number | null;
          budget_min_cents?: number | null;
          created_at?: string;
          error?: string | null;
          finished_at?: string | null;
          id?: string;
          kind?: string;
          look_mode?: string | null;
          look_types?: Json | null;
          notes?: string | null;
          occasion?: Database["public"]["Enums"]["occasion"] | null;
          pages_checked?: number;
          provider?: string;
          query: string;
          started_at?: string | null;
          status?: Database["public"]["Enums"]["job_status"];
          summary?: string | null;
          use_gpt?: boolean;
          user_id?: string;
        };
        Update: {
          budget_max_cents?: number | null;
          budget_min_cents?: number | null;
          created_at?: string;
          error?: string | null;
          finished_at?: string | null;
          id?: string;
          kind?: string;
          look_mode?: string | null;
          look_types?: Json | null;
          notes?: string | null;
          occasion?: Database["public"]["Enums"]["occasion"] | null;
          pages_checked?: number;
          provider?: string;
          query?: string;
          started_at?: string | null;
          status?: Database["public"]["Enums"]["job_status"];
          summary?: string | null;
          use_gpt?: boolean;
          user_id?: string;
        };
        Relationships: [];
      };
      item_embeddings: {
        Row: {
          created_at: string;
          embedding: string;
          item_id: string;
          model: string;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          embedding: string;
          item_id: string;
          model: string;
          user_id?: string;
        };
        Update: {
          created_at?: string;
          embedding?: string;
          item_id?: string;
          model?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "item_embeddings_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: true;
            referencedRelation: "item_stats";
            referencedColumns: ["item_id"];
          },
          {
            foreignKeyName: "item_embeddings_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: true;
            referencedRelation: "items";
            referencedColumns: ["id"];
          },
        ];
      };
      items: {
        Row: {
          bought_on: string | null;
          brand: string | null;
          category: Database["public"]["Enums"]["item_category"] | null;
          color_hex: string | null;
          color_name: string | null;
          created_at: string;
          cutout_path: string | null;
          fit: string | null;
          formality: number | null;
          id: string;
          is_sample: boolean;
          label_path: string | null;
          name: string;
          notes: string | null;
          occasions: Database["public"]["Enums"]["occasion"][];
          pattern: string | null;
          photo_path: string | null;
          price_cents: number | null;
          secondary_color: string | null;
          size: string | null;
          status: Database["public"]["Enums"]["item_status"];
          store: string | null;
          studio_path: string | null;
          suggestions: Json | null;
          tags_status: string;
          thumb_path: string | null;
          type: string | null;
          updated_at: string;
          user_id: string;
          warmth: string | null;
        };
        ComputedFields: never;
        Insert: {
          bought_on?: string | null;
          brand?: string | null;
          category?: Database["public"]["Enums"]["item_category"] | null;
          color_hex?: string | null;
          color_name?: string | null;
          created_at?: string;
          cutout_path?: string | null;
          fit?: string | null;
          formality?: number | null;
          id?: string;
          is_sample?: boolean;
          label_path?: string | null;
          name: string;
          notes?: string | null;
          occasions?: Database["public"]["Enums"]["occasion"][];
          pattern?: string | null;
          photo_path?: string | null;
          price_cents?: number | null;
          secondary_color?: string | null;
          size?: string | null;
          status?: Database["public"]["Enums"]["item_status"];
          store?: string | null;
          studio_path?: string | null;
          suggestions?: Json | null;
          tags_status?: string;
          thumb_path?: string | null;
          type?: string | null;
          updated_at?: string;
          user_id?: string;
          warmth?: string | null;
        };
        Update: {
          bought_on?: string | null;
          brand?: string | null;
          category?: Database["public"]["Enums"]["item_category"] | null;
          color_hex?: string | null;
          color_name?: string | null;
          created_at?: string;
          cutout_path?: string | null;
          fit?: string | null;
          formality?: number | null;
          id?: string;
          is_sample?: boolean;
          label_path?: string | null;
          name?: string;
          notes?: string | null;
          occasions?: Database["public"]["Enums"]["occasion"][];
          pattern?: string | null;
          photo_path?: string | null;
          price_cents?: number | null;
          secondary_color?: string | null;
          size?: string | null;
          status?: Database["public"]["Enums"]["item_status"];
          store?: string | null;
          studio_path?: string | null;
          suggestions?: Json | null;
          tags_status?: string;
          thumb_path?: string | null;
          type?: string | null;
          updated_at?: string;
          user_id?: string;
          warmth?: string | null;
        };
        Relationships: [];
      };
      jobs: {
        Row: {
          attempts: number;
          created_at: string;
          error: string | null;
          finished_at: string | null;
          id: string;
          kind: string;
          payload: NonNullable<Json>;
          priority: number;
          result: Json | null;
          started_at: string | null;
          status: Database["public"]["Enums"]["job_status"];
          user_id: string;
          worker_id: string | null;
        };
        ComputedFields: never;
        Insert: {
          attempts?: number;
          created_at?: string;
          error?: string | null;
          finished_at?: string | null;
          id?: string;
          kind: string;
          payload?: NonNullable<Json>;
          priority?: number;
          result?: Json | null;
          started_at?: string | null;
          status?: Database["public"]["Enums"]["job_status"];
          user_id?: string;
          worker_id?: string | null;
        };
        Update: {
          attempts?: number;
          created_at?: string;
          error?: string | null;
          finished_at?: string | null;
          id?: string;
          kind?: string;
          payload?: NonNullable<Json>;
          priority?: number;
          result?: Json | null;
          started_at?: string | null;
          status?: Database["public"]["Enums"]["job_status"];
          user_id?: string;
          worker_id?: string | null;
        };
        Relationships: [];
      };
      model_versions: {
        Row: {
          active: boolean;
          artifact_path: string | null;
          id: string;
          kind: string;
          metrics: NonNullable<Json>;
          sample_count: number;
          trained_at: string;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          active?: boolean;
          artifact_path?: string | null;
          id?: string;
          kind: string;
          metrics?: NonNullable<Json>;
          sample_count?: number;
          trained_at?: string;
          user_id?: string;
        };
        Update: {
          active?: boolean;
          artifact_path?: string | null;
          id?: string;
          kind?: string;
          metrics?: NonNullable<Json>;
          sample_count?: number;
          trained_at?: string;
          user_id?: string;
        };
        Relationships: [];
      };
      outfit_items: {
        Row: {
          item_id: string;
          outfit_id: string;
          position: number;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          item_id: string;
          outfit_id: string;
          position?: number;
          user_id?: string;
        };
        Update: {
          item_id?: string;
          outfit_id?: string;
          position?: number;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "outfit_items_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: false;
            referencedRelation: "item_stats";
            referencedColumns: ["item_id"];
          },
          {
            foreignKeyName: "outfit_items_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: false;
            referencedRelation: "items";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "outfit_items_outfit_id_fkey";
            columns: ["outfit_id"];
            isOneToOne: false;
            referencedRelation: "outfit_stats";
            referencedColumns: ["outfit_id"];
          },
          {
            foreignKeyName: "outfit_items_outfit_id_fkey";
            columns: ["outfit_id"];
            isOneToOne: false;
            referencedRelation: "outfits";
            referencedColumns: ["id"];
          },
        ];
      };
      outfits: {
        Row: {
          created_at: string;
          id: string;
          name: string | null;
          occasions: Database["public"]["Enums"]["occasion"][];
          source: string;
          updated_at: string;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          id?: string;
          name?: string | null;
          occasions?: Database["public"]["Enums"]["occasion"][];
          source?: string;
          updated_at?: string;
          user_id?: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          name?: string | null;
          occasions?: Database["public"]["Enums"]["occasion"][];
          source?: string;
          updated_at?: string;
          user_id?: string;
        };
        Relationships: [];
      };
      paid_usage: {
        Row: {
          created_at: string;
          est_cost_usd: number;
          feature: string;
          id: string;
          input_tokens: number;
          model: string | null;
          output_tokens: number;
          user_id: string;
          web_search_calls: number;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          est_cost_usd?: number;
          feature: string;
          id?: string;
          input_tokens?: number;
          model?: string | null;
          output_tokens?: number;
          user_id?: string;
          web_search_calls?: number;
        };
        Update: {
          created_at?: string;
          est_cost_usd?: number;
          feature?: string;
          id?: string;
          input_tokens?: number;
          model?: string | null;
          output_tokens?: number;
          user_id?: string;
          web_search_calls?: number;
        };
        Relationships: [];
      };
      price_checks: {
        Row: {
          checked_at: string;
          id: string;
          in_stock: boolean | null;
          note: string | null;
          price_cents: number | null;
          source: string | null;
          user_id: string;
          wishlist_id: string;
        };
        ComputedFields: never;
        Insert: {
          checked_at?: string;
          id?: string;
          in_stock?: boolean | null;
          note?: string | null;
          price_cents?: number | null;
          source?: string | null;
          user_id?: string;
          wishlist_id: string;
        };
        Update: {
          checked_at?: string;
          id?: string;
          in_stock?: boolean | null;
          note?: string | null;
          price_cents?: number | null;
          source?: string | null;
          user_id?: string;
          wishlist_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "price_checks_wishlist_id_fkey";
            columns: ["wishlist_id"];
            isOneToOne: false;
            referencedRelation: "wishlist_items";
            referencedColumns: ["id"];
          },
        ];
      };
      profiles: {
        Row: {
          analysis: Json | null;
          analyzed_at: string | null;
          city_name: string | null;
          contrast_override: string | null;
          created_at: string;
          favorite_stores: string[];
          fit_pref: string;
          height_cm: number | null;
          latitude: number | null;
          longitude: number | null;
          monthly_budget_cents: number;
          paid_monthly_cap_cents: number;
          sizes: NonNullable<Json>;
          temp_unit: string;
          timezone: string;
          undertone_override: string | null;
          updated_at: string;
          user_id: string;
          wears: string | null;
        };
        ComputedFields: never;
        Insert: {
          analysis?: Json | null;
          analyzed_at?: string | null;
          city_name?: string | null;
          contrast_override?: string | null;
          created_at?: string;
          favorite_stores?: string[];
          fit_pref?: string;
          height_cm?: number | null;
          latitude?: number | null;
          longitude?: number | null;
          monthly_budget_cents?: number;
          paid_monthly_cap_cents?: number;
          sizes?: NonNullable<Json>;
          temp_unit?: string;
          timezone?: string;
          undertone_override?: string | null;
          updated_at?: string;
          user_id?: string;
          wears?: string | null;
        };
        Update: {
          analysis?: Json | null;
          analyzed_at?: string | null;
          city_name?: string | null;
          contrast_override?: string | null;
          created_at?: string;
          favorite_stores?: string[];
          fit_pref?: string;
          height_cm?: number | null;
          latitude?: number | null;
          longitude?: number | null;
          monthly_budget_cents?: number;
          paid_monthly_cap_cents?: number;
          sizes?: NonNullable<Json>;
          temp_unit?: string;
          timezone?: string;
          undertone_override?: string | null;
          updated_at?: string;
          user_id?: string;
          wears?: string | null;
        };
        Relationships: [];
      };
      style_photos: {
        Row: {
          created_at: string;
          id: string;
          kind: string;
          photo_path: string;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          id?: string;
          kind: string;
          photo_path: string;
          user_id?: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          kind?: string;
          photo_path?: string;
          user_id?: string;
        };
        Relationships: [];
      };
      suggestion_events: {
        Row: {
          action: string;
          context: NonNullable<Json>;
          created_at: string;
          id: string;
          item_ids: string[];
          model_version: string | null;
          occasion: Database["public"]["Enums"]["occasion"];
          score: number | null;
          user_id: string;
        };
        ComputedFields: never;
        Insert: {
          action: string;
          context?: NonNullable<Json>;
          created_at?: string;
          id?: string;
          item_ids: string[];
          model_version?: string | null;
          occasion: Database["public"]["Enums"]["occasion"];
          score?: number | null;
          user_id?: string;
        };
        Update: {
          action?: string;
          context?: NonNullable<Json>;
          created_at?: string;
          id?: string;
          item_ids?: string[];
          model_version?: string | null;
          occasion?: Database["public"]["Enums"]["occasion"];
          score?: number | null;
          user_id?: string;
        };
        Relationships: [];
      };
      wear_log_items: {
        Row: {
          item_id: string;
          user_id: string;
          wear_log_id: string;
        };
        ComputedFields: never;
        Insert: {
          item_id: string;
          user_id?: string;
          wear_log_id: string;
        };
        Update: {
          item_id?: string;
          user_id?: string;
          wear_log_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: "wear_log_items_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: false;
            referencedRelation: "item_stats";
            referencedColumns: ["item_id"];
          },
          {
            foreignKeyName: "wear_log_items_item_id_fkey";
            columns: ["item_id"];
            isOneToOne: false;
            referencedRelation: "items";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "wear_log_items_wear_log_id_fkey";
            columns: ["wear_log_id"];
            isOneToOne: false;
            referencedRelation: "wear_logs";
            referencedColumns: ["id"];
          },
        ];
      };
      wear_logs: {
        Row: {
          created_at: string;
          id: string;
          occasion: Database["public"]["Enums"]["occasion"];
          outfit_id: string | null;
          user_id: string;
          worn_on: string;
        };
        ComputedFields: never;
        Insert: {
          created_at?: string;
          id?: string;
          occasion: Database["public"]["Enums"]["occasion"];
          outfit_id?: string | null;
          user_id?: string;
          worn_on: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          occasion?: Database["public"]["Enums"]["occasion"];
          outfit_id?: string | null;
          user_id?: string;
          worn_on?: string;
        };
        Relationships: [
          {
            foreignKeyName: "wear_logs_outfit_id_fkey";
            columns: ["outfit_id"];
            isOneToOne: false;
            referencedRelation: "outfit_stats";
            referencedColumns: ["outfit_id"];
          },
          {
            foreignKeyName: "wear_logs_outfit_id_fkey";
            columns: ["outfit_id"];
            isOneToOne: false;
            referencedRelation: "outfits";
            referencedColumns: ["id"];
          },
        ];
      };
      wishlist_items: {
        Row: {
          category: Database["public"]["Enums"]["item_category"] | null;
          check_result: Json | null;
          checked_at: string | null;
          color_name: string | null;
          created_at: string;
          embedding: string | null;
          id: string;
          image_url: string | null;
          last_price_check_at: string | null;
          last_seen_price_cents: number | null;
          name: string;
          notes: string | null;
          occasion: Database["public"]["Enums"]["occasion"] | null;
          photo_path: string | null;
          price_cents: number | null;
          status: string;
          store: string | null;
          target_price_cents: number | null;
          url: string | null;
          user_id: string;
          watch: boolean;
        };
        ComputedFields: never;
        Insert: {
          category?: Database["public"]["Enums"]["item_category"] | null;
          check_result?: Json | null;
          checked_at?: string | null;
          color_name?: string | null;
          created_at?: string;
          embedding?: string | null;
          id?: string;
          image_url?: string | null;
          last_price_check_at?: string | null;
          last_seen_price_cents?: number | null;
          name: string;
          notes?: string | null;
          occasion?: Database["public"]["Enums"]["occasion"] | null;
          photo_path?: string | null;
          price_cents?: number | null;
          status?: string;
          store?: string | null;
          target_price_cents?: number | null;
          url?: string | null;
          user_id?: string;
          watch?: boolean;
        };
        Update: {
          category?: Database["public"]["Enums"]["item_category"] | null;
          check_result?: Json | null;
          checked_at?: string | null;
          color_name?: string | null;
          created_at?: string;
          embedding?: string | null;
          id?: string;
          image_url?: string | null;
          last_price_check_at?: string | null;
          last_seen_price_cents?: number | null;
          name?: string;
          notes?: string | null;
          occasion?: Database["public"]["Enums"]["occasion"] | null;
          photo_path?: string | null;
          price_cents?: number | null;
          status?: string;
          store?: string | null;
          target_price_cents?: number | null;
          url?: string | null;
          user_id?: string;
          watch?: boolean;
        };
        Relationships: [];
      };
      workers: {
        Row: {
          capabilities: NonNullable<Json>;
          id: string;
          last_seen_at: string;
          user_id: string;
          version: string | null;
        };
        ComputedFields: never;
        Insert: {
          capabilities?: NonNullable<Json>;
          id: string;
          last_seen_at?: string;
          user_id?: string;
          version?: string | null;
        };
        Update: {
          capabilities?: NonNullable<Json>;
          id?: string;
          last_seen_at?: string;
          user_id?: string;
          version?: string | null;
        };
        Relationships: [];
      };
    };
    Views: {
      item_stats: {
        Row: {
          cost_per_wear_cents: number | null;
          item_id: string;
          last_worn_on: string | null;
          user_id: string;
          wear_count: number | null;
        };
        ComputedFields: never;
        Relationships: [];
      };
      monthly_spend: {
        Row: {
          category: Database["public"]["Enums"]["item_category"] | null;
          item_count: number | null;
          month: string | null;
          total_cents: number | null;
          user_id: string;
        };
        ComputedFields: never;
        Relationships: [];
      };
      outfit_stats: {
        Row: {
          last_worn_on: string | null;
          outfit_id: string;
          user_id: string;
          wear_count: number | null;
        };
        ComputedFields: never;
        Relationships: [];
      };
    };
    Functions: {
      category_rank: { Args: { c: Database["public"]["Enums"]["item_category"] }; Returns: number };
      claim_job: {
        Args: { p_user?: string; p_worker: string };
        Returns: {
          attempts: number;
          created_at: string;
          error: string | null;
          finished_at: string | null;
          id: string;
          kind: string;
          payload: NonNullable<Json>;
          priority: number;
          result: Json | null;
          started_at: string | null;
          status: Database["public"]["Enums"]["job_status"];
          user_id: string;
          worker_id: string | null;
        }[];
        SetofOptions: {
          from: "*";
          to: "jobs";
          isOneToOne: false;
          isSetofReturn: true;
        };
      };
      delete_all_my_data: { Args: Record<PropertyKey, never>; Returns: undefined };
      log_wear: {
        Args: {
          p_item_ids: string[];
          p_occasion: Database["public"]["Enums"]["occasion"];
          p_outfit_id: string;
          p_worn_on: string;
        };
        Returns: Json;
      };
      nearest_items: {
        Args: {
          p_category?: Database["public"]["Enums"]["item_category"];
          p_embedding: string;
          p_k?: number;
          p_owner: string;
        };
        Returns: {
          item_id: string;
          similarity: number;
        }[];
      };
      requeue_stale_jobs: { Args: Record<PropertyKey, never>; Returns: number };
      save_outfit: {
        Args: {
          p_id: string;
          p_item_ids: string[];
          p_name: string;
          p_occasions: Database["public"]["Enums"]["occasion"][];
          p_source?: string;
        };
        Returns: string;
      };
    };
    Enums: {
      item_category: "Tops" | "Bottoms" | "Layers" | "Shoes" | "Accessories" | "Sets & suits";
      item_status: "active" | "laundry" | "retired";
      job_status: "queued" | "running" | "done" | "failed";
      occasion: "office" | "college" | "party" | "home";
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
};

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">;

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">];

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    keyof (DefaultSchema["Tables"] & DefaultSchema["Views"]) | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R;
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] & DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R;
      }
      ? R
      : never
    : never;

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"] | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I;
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I;
      }
      ? I
      : never
    : never;

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"] | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U;
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U;
      }
      ? U
      : never
    : never;

export type Enums<
  DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"] | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never;

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    keyof DefaultSchema["CompositeTypes"] | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never;

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {
      item_category: ["Tops", "Bottoms", "Layers", "Shoes", "Accessories", "Sets & suits"],
      item_status: ["active", "laundry", "retired"],
      job_status: ["queued", "running", "done", "failed"],
      occasion: ["office", "college", "party", "home"],
    },
  },
} as const;
