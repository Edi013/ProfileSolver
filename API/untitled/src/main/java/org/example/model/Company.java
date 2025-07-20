package org.example.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.elasticsearch.annotations.Document;

import java.util.List;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Document(indexName = "companies")
public class Company {

    @Id
    private String companyId;  // ES document id, mapped from your DB id

    private String names;

    private String email;
    private String phone;
    private String website;
    private String facebookProfile;

    private List<Map<String, Object>> urls;  // Store urls as list of maps, e.g. [{"url":"x","reached":true}]
}
