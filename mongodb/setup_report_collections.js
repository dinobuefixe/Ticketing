

const d = db.getSiblingDB(process.env.DB);
const INT = ["int", "long"];

function ensureCollection(name, schema) {
  const opts = {
    validator: { $jsonSchema: schema },
    validationLevel: "strict",
    validationAction: "error"
  };
  if (d.getCollectionNames().includes(name)) {
    d.runCommand({ collMod: name, ...opts });
    print("coleção atualizada: " + name);
  } else {
    d.createCollection(name, opts);
    print("coleção criada: " + name);
  }
}

ensureCollection("report_orders", {
  bsonType: "object",
  required: ["_id", "status", "performance_id", "paid_at", "total_cents", "discount_cents",
             "event_id", "event_title", "organiser_id", "venue_id", "city", "tickets", "exported_at"],
  properties: {
    _id:            { bsonType: "string", description: "UUID da encomenda" },
    status:         { enum: ["paid", "refunded"] },
    performance_id: { bsonType: "string" },
    paid_at:        { bsonType: ["date", "null"] },
    total_cents:    { bsonType: INT, description: "total pago, em cêntimos" },
    discount_cents: { bsonType: INT, description: "desconto do código promocional, em cêntimos" },
    event_id:       { bsonType: "string" },
    event_title:    { bsonType: "string" },
    organiser_id:   { bsonType: "string" },
    venue_id:       { bsonType: "string" },
    city:           { bsonType: "string" },
    promo_code:     { bsonType: ["string", "null"] },
    method:         { bsonType: ["string", "null"], description: "método do pagamento aprovado" },
    tickets: {
      bsonType: "array",
      items: {
        bsonType: "object",
        required: ["section_id", "price_cents", "status"],
        properties: {
          section_id:  { bsonType: "string" },
          price_cents: { bsonType: INT },
          status:      { enum: ["valid", "used", "cancelled"] }
        }
      }
    },
    exported_at:    { bsonType: "date" }
  }
});

ensureCollection("report_performances", {
  bsonType: "object",
  required: ["_id", "status", "starts_at", "event_id", "event_title", "category", "venue_id",
             "venue_name", "city", "seated_capacity", "standing_capacity", "sections",
             "checked_in", "tickets_sold", "gross_cents", "exported_at"],
  properties: {
    _id:               { bsonType: "string", description: "UUID da performance" },
    status:            { enum: ["scheduled", "on_sale", "sold_out", "finished", "cancelled"] },
    starts_at:         { bsonType: "date" },
    event_id:          { bsonType: "string" },
    event_title:       { bsonType: "string" },
    category:          { enum: ["concert", "theatre", "comedy", "sport", "other"] },
    venue_id:          { bsonType: "string" },
    venue_name:        { bsonType: "string" },
    city:              { bsonType: "string" },
    seated_capacity:   { bsonType: INT },
    standing_capacity: { bsonType: INT },
    checked_in:        { bsonType: INT },
    tickets_sold:      { bsonType: INT },
    gross_cents:       { bsonType: INT },
    sections: {
      bsonType: "array",
      items: {
        bsonType: "object",
        required: ["section_id", "name", "kind", "sold", "gross_cents"],
        properties: {
          section_id:  { bsonType: "string" },
          name:        { bsonType: "string" },
          kind:        { enum: ["seated", "standing"] },
          sold:        { bsonType: INT },
          gross_cents: { bsonType: INT }
        }
      }
    },
    exported_at:       { bsonType: "date" }
  }
});

d.getCollection("report_orders").createIndex(
  { status: 1, paid_at: 1 }, { name: "status_paid_at" });
d.getCollection("report_performances").createIndex(
  { status: 1, starts_at: 1 }, { name: "status_starts_at" });
print("índices prontos nas coleções de relatório");