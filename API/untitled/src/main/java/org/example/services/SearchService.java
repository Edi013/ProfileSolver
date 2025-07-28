package org.example.services;

import org.example.model.Company;
import org.example.repository.CompanyRepository;
import org.springframework.stereotype.Service;
import org.apache.commons.text.StringEscapeUtils;


import java.util.List;

@Service
public class SearchService {

    private final CompanyRepository companyRepository;

    public SearchService(CompanyRepository companyRepository) {
        this.companyRepository = companyRepository;
    }

    public List<Company> searchCompanies(String query) {
        String sanitizedQuery = sanitize(query);
        return companyRepository.findByNamesContainingIgnoreCaseOrEmailContainingIgnoreCaseOrPhoneContainingIgnoreCase(
                sanitizedQuery, sanitizedQuery, sanitizedQuery);
    }

    private String sanitize(String input) {
        if (input == null) {
            return "";
        }
        return StringEscapeUtils.escapeJava(input.trim());
    }

}
