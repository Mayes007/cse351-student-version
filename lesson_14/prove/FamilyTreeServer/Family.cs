using System.Text.Json.Serialization;

namespace Assignment14;

public class Family
{
    [JsonPropertyName("id")]
    public long Id { get; set; }

    [JsonPropertyName("husband_id")]
    public long HusbandId { get; set; }

    [JsonPropertyName("wife_id")]
    public long WifeId { get; set; }

    [JsonPropertyName("children")]
    public List<long> Children { get; set; } = new();
}
