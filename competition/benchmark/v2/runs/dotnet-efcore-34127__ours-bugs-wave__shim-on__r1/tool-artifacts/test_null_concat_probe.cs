// Probe to test whether AssertQuery handles string + null correctly
using System;
using System.Collections.Generic;
using System.Linq;

public class StringConcatNullProbe
{
    public static void Main()
    {
        var entities = new List<Entity>
        {
            new() { Id = 1, A = "Foo", B = "Bar", C = null },
            new() { Id = 2, A = "Foo", B = "Bar", C = "Baz" },
            new() { Id = 3, A = "Foo", B = null, C = "Baz" },
            new() { Id = 4, A = null, B = "Bar", C = "Baz" },
        };

        Console.WriteLine("Testing in-memory LINQ-to-Objects string concatenation with null:");

        try
        {
            var result = entities.Select(x =>
                x.A != null && x.B != null
                    ? x.A + x.B + x.C
                    : null).ToList();

            Console.WriteLine("Success!");
            foreach (var item in result)
            {
                Console.WriteLine($"  {item}");
            }
        }
        catch (NullReferenceException ex)
        {
            Console.WriteLine($"FAILED with NullReferenceException: {ex.Message}");
            Console.WriteLine("This means the test would fail when trying to concatenate non-null strings with null!");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"FAILED with {ex.GetType().Name}: {ex.Message}");
        }
    }
}

public class Entity
{
    public int Id { get; set; }
    public string A { get; set; }
    public string B { get; set; }
    public string C { get; set; }
}
